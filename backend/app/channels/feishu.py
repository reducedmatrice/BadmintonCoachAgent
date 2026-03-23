"""Feishu/Lark channel — connects to Feishu via WebSocket (no public IP needed)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

from app.channels.base import Channel
from app.channels.message_bus import InboundMessageType, MessageBus, OutboundMessage, ResolvedAttachment

logger = logging.getLogger(__name__)


class FeishuChannel(Channel):
    """Feishu/Lark IM channel using the ``lark-oapi`` WebSocket client.

    Configuration keys (in ``config.yaml`` under ``channels.feishu``):
        - ``app_id``: Feishu app ID.
        - ``app_secret``: Feishu app secret.
        - ``verification_token``: (optional) Event verification token.

    The channel uses WebSocket long-connection mode so no public IP is required.

    Message flow:
        1. User sends a message → bot adds "OK" emoji reaction
        2. Bot replies in thread: "Working on it......"
        3. Agent processes the message and returns a result
        4. Bot replies in thread with the result
        5. Bot adds "DONE" emoji reaction to the original message
    """

    def __init__(self, bus: MessageBus, config: dict[str, Any]) -> None:
        super().__init__(name="feishu", bus=bus, config=config)
        self._thread: threading.Thread | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._api_client = None
        self._CreateMessageReactionRequest = None
        self._CreateMessageReactionRequestBody = None
        self._Emoji = None
        self._PatchMessageRequest = None
        self._PatchMessageRequestBody = None
        self._background_tasks: set[asyncio.Task] = set()
        self._running_card_ids: dict[str, str] = {}
        self._running_card_tasks: dict[str, asyncio.Task] = {}
        self._CreateFileRequest = None
        self._CreateFileRequestBody = None
        self._CreateImageRequest = None
        self._CreateImageRequestBody = None

    async def start(self) -> None:
        if self._running:
            return

        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import (
                CreateFileRequest,
                CreateFileRequestBody,
                CreateImageRequest,
                CreateImageRequestBody,
                CreateMessageReactionRequest,
                CreateMessageReactionRequestBody,
                CreateMessageRequest,
                CreateMessageRequestBody,
                Emoji,
                PatchMessageRequest,
                PatchMessageRequestBody,
                ReplyMessageRequest,
                ReplyMessageRequestBody,
            )
        except ImportError:
            logger.error("lark-oapi is not installed. Install it with: uv add lark-oapi")
            return

        self._lark = lark
        self._CreateMessageRequest = CreateMessageRequest
        self._CreateMessageRequestBody = CreateMessageRequestBody
        self._ReplyMessageRequest = ReplyMessageRequest
        self._ReplyMessageRequestBody = ReplyMessageRequestBody
        self._CreateMessageReactionRequest = CreateMessageReactionRequest
        self._CreateMessageReactionRequestBody = CreateMessageReactionRequestBody
        self._Emoji = Emoji
        self._PatchMessageRequest = PatchMessageRequest
        self._PatchMessageRequestBody = PatchMessageRequestBody
        self._CreateFileRequest = CreateFileRequest
        self._CreateFileRequestBody = CreateFileRequestBody
        self._CreateImageRequest = CreateImageRequest
        self._CreateImageRequestBody = CreateImageRequestBody

        app_id = self.config.get("app_id", "")
        app_secret = self.config.get("app_secret", "")

        if not app_id or not app_secret:
            logger.error("Feishu channel requires app_id and app_secret")
            return

        self._api_client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        self._main_loop = asyncio.get_event_loop()

        self._running = True
        self.bus.subscribe_outbound(self._on_outbound)

        # Both ws.Client construction and start() must happen in a dedicated
        # thread with its own event loop.  lark-oapi caches the running loop
        # at construction time and later calls loop.run_until_complete(),
        # which conflicts with an already-running uvloop.
        self._thread = threading.Thread(
            target=self._run_ws,
            args=(app_id, app_secret),
            daemon=True,
        )
        self._thread.start()
        logger.info("Feishu channel started")

    def _run_ws(self, app_id: str, app_secret: str) -> None:
        """Construct and run the lark WS client in a thread with a fresh event loop.

        The lark-oapi SDK captures a module-level event loop at import time
        (``lark_oapi.ws.client.loop``).  When uvicorn uses uvloop, that
        captured loop is the *main* thread's uvloop — which is already
        running, so ``loop.run_until_complete()`` inside ``Client.start()``
        raises ``RuntimeError``.

        We work around this by creating a plain asyncio event loop for this
        thread and patching the SDK's module-level reference before calling
        ``start()``.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import lark_oapi as lark
            import lark_oapi.ws.client as _ws_client_mod

            # Replace the SDK's module-level loop so Client.start() uses
            # this thread's (non-running) event loop instead of the main
            # thread's uvloop.
            _ws_client_mod.loop = loop

            event_handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(self._on_message).build()
            ws_client = lark.ws.Client(
                app_id=app_id,
                app_secret=app_secret,
                event_handler=event_handler,
                log_level=lark.LogLevel.INFO,
            )
            ws_client.start()
        except Exception:
            if self._running:
                logger.exception("Feishu WebSocket error")

    async def stop(self) -> None:
        self._running = False
        self.bus.unsubscribe_outbound(self._on_outbound)
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        for task in list(self._running_card_tasks.values()):
            task.cancel()
        self._running_card_tasks.clear()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Feishu channel stopped")

    async def send(self, msg: OutboundMessage, *, _max_retries: int = 3) -> None:
        if not self._api_client:
            logger.warning("[Feishu] send called but no api_client available")
            return

        logger.info(
            "[Feishu] sending reply: chat_id=%s, thread_ts=%s, text_len=%d",
            msg.chat_id,
            msg.thread_ts,
            len(msg.text),
        )

        last_exc: Exception | None = None
        for attempt in range(_max_retries):
            try:
                await self._send_card_message(msg)
                return  # success
            except Exception as exc:
                last_exc = exc
                if attempt < _max_retries - 1:
                    delay = 2**attempt  # 1s, 2s
                    logger.warning(
                        "[Feishu] send failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        _max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        logger.error("[Feishu] send failed after %d attempts: %s", _max_retries, last_exc)
        raise last_exc  # type: ignore[misc]

    async def send_file(self, msg: OutboundMessage, attachment: ResolvedAttachment) -> bool:
        if not self._api_client:
            return False

        # Check size limits (image: 10MB, file: 30MB)
        if attachment.is_image and attachment.size > 10 * 1024 * 1024:
            logger.warning("[Feishu] image too large (%d bytes), skipping: %s", attachment.size, attachment.filename)
            return False
        if not attachment.is_image and attachment.size > 30 * 1024 * 1024:
            logger.warning("[Feishu] file too large (%d bytes), skipping: %s", attachment.size, attachment.filename)
            return False

        try:
            if attachment.is_image:
                file_key = await self._upload_image(attachment.actual_path)
                msg_type = "image"
                content = json.dumps({"image_key": file_key})
            else:
                file_key = await self._upload_file(attachment.actual_path, attachment.filename)
                msg_type = "file"
                content = json.dumps({"file_key": file_key})

            if msg.thread_ts:
                request = self._ReplyMessageRequest.builder().message_id(msg.thread_ts).request_body(self._ReplyMessageRequestBody.builder().msg_type(msg_type).content(content).reply_in_thread(True).build()).build()
                await asyncio.to_thread(self._api_client.im.v1.message.reply, request)
            else:
                request = self._CreateMessageRequest.builder().receive_id_type("chat_id").request_body(self._CreateMessageRequestBody.builder().receive_id(msg.chat_id).msg_type(msg_type).content(content).build()).build()
                await asyncio.to_thread(self._api_client.im.v1.message.create, request)

            logger.info("[Feishu] file sent: %s (type=%s)", attachment.filename, msg_type)
            return True
        except Exception:
            logger.exception("[Feishu] failed to upload/send file: %s", attachment.filename)
            return False

    async def _upload_image(self, path) -> str:
        """Upload an image to Feishu and return the image_key."""
        with open(str(path), "rb") as f:
            request = self._CreateImageRequest.builder().request_body(self._CreateImageRequestBody.builder().image_type("message").image(f).build()).build()
            response = await asyncio.to_thread(self._api_client.im.v1.image.create, request)
        if not response.success():
            raise RuntimeError(f"Feishu image upload failed: code={response.code}, msg={response.msg}")
        return response.data.image_key

    async def _upload_file(self, path, filename: str) -> str:
        """Upload a file to Feishu and return the file_key."""
        suffix = path.suffix.lower() if hasattr(path, "suffix") else ""
        if suffix in (".xls", ".xlsx", ".csv"):
            file_type = "xls"
        elif suffix in (".ppt", ".pptx"):
            file_type = "ppt"
        elif suffix == ".pdf":
            file_type = "pdf"
        elif suffix in (".doc", ".docx"):
            file_type = "doc"
        else:
            file_type = "stream"

        with open(str(path), "rb") as f:
            request = self._CreateFileRequest.builder().request_body(self._CreateFileRequestBody.builder().file_type(file_type).file_name(filename).file(f).build()).build()
            response = await asyncio.to_thread(self._api_client.im.v1.file.create, request)
        if not response.success():
            raise RuntimeError(f"Feishu file upload failed: code={response.code}, msg={response.msg}")
        return response.data.file_key

    # -- message formatting ------------------------------------------------

    @staticmethod
    def _build_card_content(text: str) -> str:
        """Build a Feishu interactive card with stable coach-oriented sections."""
        title, sections = FeishuChannel._split_card_sections(text)
        card = {
            "config": {"wide_screen_mode": True, "update_multi": True},
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "markdown", "content": content} for content in sections],
        }
        return json.dumps(card, ensure_ascii=False)

    @staticmethod
    def _split_card_sections(text: str) -> tuple[str, list[str]]:
        title = "Badminton Coach"
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines and lines[0].startswith("#"):
            title = lines.pop(0).lstrip("# ").strip() or title

        buckets: dict[str, list[str]] = {
            "建议摘要": [],
            "重点项": [],
            "热身建议": [],
            "风险提示": [],
            "下次建议": [],
        }
        current_section = "建议摘要"

        for line in lines:
            normalized = line.lstrip("-* ").strip()
            section, content = FeishuChannel._match_card_section(normalized)
            if section:
                current_section = section
                if content:
                    buckets[current_section].append(content)
                continue
            buckets[current_section].append(normalized)

        if not any(buckets.values()):
            buckets["建议摘要"].append(text.strip() or "Working on it...")

        ordered_sections = []
        for section_name in ("建议摘要", "重点项", "热身建议", "风险提示", "下次建议"):
            items = [item for item in buckets[section_name] if item]
            if not items:
                continue
            ordered_sections.append(FeishuChannel._render_card_section(section_name, items))
        return title, ordered_sections

    @staticmethod
    def _match_card_section(line: str) -> tuple[str | None, str]:
        normalized = line.strip().lstrip("# ").strip()
        mappings = {
            "重点项": ("重点项", "训练重点", "今日重点", "重点"),
            "热身建议": ("热身建议", "热身"),
            "风险提示": ("风险提示", "风险", "提醒"),
            "下次建议": ("下次建议", "下一步", "下次重点", "后续建议"),
        }
        for section, prefixes in mappings.items():
            for prefix in prefixes:
                if normalized == prefix:
                    return section, ""
                for separator in ("：", ":"):
                    marker = f"{prefix}{separator}"
                    if normalized.startswith(marker):
                        return section, normalized[len(marker) :].strip()
        return None, ""

    @staticmethod
    def _render_card_section(section_name: str, items: list[str]) -> str:
        if section_name == "建议摘要" and len(items) == 1:
            return f"**{section_name}**\n{items[0]}"
        bullet_lines = "\n".join(f"- {item}" for item in items)
        return f"**{section_name}**\n{bullet_lines}"

    # -- reaction helpers --------------------------------------------------

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """Add an emoji reaction to a message."""
        if not self._api_client or not self._CreateMessageReactionRequest:
            return
        try:
            request = self._CreateMessageReactionRequest.builder().message_id(message_id).request_body(self._CreateMessageReactionRequestBody.builder().reaction_type(self._Emoji.builder().emoji_type(emoji_type).build()).build()).build()
            await asyncio.to_thread(self._api_client.im.v1.message_reaction.create, request)
            logger.info("[Feishu] reaction '%s' added to message %s", emoji_type, message_id)
        except Exception:
            logger.exception("[Feishu] failed to add reaction '%s' to message %s", emoji_type, message_id)

    async def _reply_card(self, message_id: str, text: str) -> str | None:
        """Reply with an interactive card and return the created card message ID."""
        if not self._api_client:
            return None

        content = self._build_card_content(text)
        request = self._ReplyMessageRequest.builder().message_id(message_id).request_body(self._ReplyMessageRequestBody.builder().msg_type("interactive").content(content).reply_in_thread(True).build()).build()
        response = await asyncio.to_thread(self._api_client.im.v1.message.reply, request)
        response_data = getattr(response, "data", None)
        return getattr(response_data, "message_id", None)

    async def _create_card(self, chat_id: str, text: str) -> None:
        """Create a new card message in the target chat."""
        if not self._api_client:
            return

        content = self._build_card_content(text)
        request = self._CreateMessageRequest.builder().receive_id_type("chat_id").request_body(self._CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("interactive").content(content).build()).build()
        await asyncio.to_thread(self._api_client.im.v1.message.create, request)

    async def _update_card(self, message_id: str, text: str) -> None:
        """Patch an existing card message in place."""
        if not self._api_client or not self._PatchMessageRequest:
            return

        content = self._build_card_content(text)
        request = self._PatchMessageRequest.builder().message_id(message_id).request_body(self._PatchMessageRequestBody.builder().content(content).build()).build()
        await asyncio.to_thread(self._api_client.im.v1.message.patch, request)

    def _track_background_task(self, task: asyncio.Task, *, name: str, msg_id: str) -> None:
        """Keep a strong reference to fire-and-forget tasks and surface errors."""
        self._background_tasks.add(task)
        task.add_done_callback(lambda done_task, task_name=name, mid=msg_id: self._finalize_background_task(done_task, task_name, mid))

    def _finalize_background_task(self, task: asyncio.Task, name: str, msg_id: str) -> None:
        self._background_tasks.discard(task)
        self._log_task_error(task, name, msg_id)

    async def _create_running_card(self, source_message_id: str, text: str) -> str | None:
        """Create the running card and cache its message ID when available."""
        running_card_id = await self._reply_card(source_message_id, text)
        if running_card_id:
            self._running_card_ids[source_message_id] = running_card_id
            logger.info("[Feishu] running card created: source=%s card=%s", source_message_id, running_card_id)
        else:
            logger.warning("[Feishu] running card creation returned no message_id for source=%s, subsequent updates will fall back to new replies", source_message_id)
        return running_card_id

    def _ensure_running_card_started(self, source_message_id: str, text: str = "Working on it...") -> asyncio.Task | None:
        """Start running-card creation once per source message."""
        running_card_id = self._running_card_ids.get(source_message_id)
        if running_card_id:
            return None

        running_card_task = self._running_card_tasks.get(source_message_id)
        if running_card_task:
            return running_card_task

        running_card_task = asyncio.create_task(self._create_running_card(source_message_id, text))
        self._running_card_tasks[source_message_id] = running_card_task
        running_card_task.add_done_callback(lambda done_task, mid=source_message_id: self._finalize_running_card_task(mid, done_task))
        return running_card_task

    def _finalize_running_card_task(self, source_message_id: str, task: asyncio.Task) -> None:
        if self._running_card_tasks.get(source_message_id) is task:
            self._running_card_tasks.pop(source_message_id, None)
        self._log_task_error(task, "create_running_card", source_message_id)

    async def _ensure_running_card(self, source_message_id: str, text: str = "Working on it...") -> str | None:
        """Ensure the in-thread running card exists and track its message ID."""
        running_card_id = self._running_card_ids.get(source_message_id)
        if running_card_id:
            return running_card_id

        running_card_task = self._ensure_running_card_started(source_message_id, text)
        if running_card_task is None:
            return self._running_card_ids.get(source_message_id)
        return await running_card_task

    async def _send_running_reply(self, message_id: str) -> None:
        """Reply to a message in-thread with a running card."""
        try:
            await self._ensure_running_card(message_id)
        except Exception:
            logger.exception("[Feishu] failed to send running reply for message %s", message_id)

    async def _send_card_message(self, msg: OutboundMessage) -> None:
        """Send or update the Feishu card tied to the current request."""
        source_message_id = msg.thread_ts
        if source_message_id:
            running_card_id = self._running_card_ids.get(source_message_id)
            awaited_running_card_task = False

            if not running_card_id:
                running_card_task = self._running_card_tasks.get(source_message_id)
                if running_card_task:
                    awaited_running_card_task = True
                    running_card_id = await running_card_task

            if running_card_id:
                try:
                    await self._update_card(running_card_id, msg.text)
                except Exception:
                    if not msg.is_final:
                        raise
                    logger.exception(
                        "[Feishu] failed to patch running card %s, falling back to final reply",
                        running_card_id,
                    )
                    await self._reply_card(source_message_id, msg.text)
                else:
                    logger.info("[Feishu] running card updated: source=%s card=%s", source_message_id, running_card_id)
            elif msg.is_final:
                await self._reply_card(source_message_id, msg.text)
            elif awaited_running_card_task:
                logger.warning(
                    "[Feishu] running card task finished without message_id for source=%s, skipping duplicate non-final creation",
                    source_message_id,
                )
            else:
                await self._ensure_running_card(source_message_id, msg.text)

            if msg.is_final:
                self._running_card_ids.pop(source_message_id, None)
                await self._add_reaction(source_message_id, "DONE")
            return

        await self._create_card(msg.chat_id, msg.text)

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _log_future_error(fut, name: str, msg_id: str) -> None:
        """Callback for run_coroutine_threadsafe futures to surface errors."""
        try:
            exc = fut.exception()
            if exc:
                logger.error("[Feishu] %s failed for msg_id=%s: %s", name, msg_id, exc)
        except Exception:
            pass

    @staticmethod
    def _log_task_error(task: asyncio.Task, name: str, msg_id: str) -> None:
        """Callback for background asyncio tasks to surface errors."""
        try:
            exc = task.exception()
            if exc:
                logger.error("[Feishu] %s failed for msg_id=%s: %s", name, msg_id, exc)
        except asyncio.CancelledError:
            logger.info("[Feishu] %s cancelled for msg_id=%s", name, msg_id)
        except Exception:
            pass

    async def _prepare_inbound(self, msg_id: str, inbound) -> None:
        """Kick off Feishu side effects without delaying inbound dispatch."""
        reaction_task = asyncio.create_task(self._add_reaction(msg_id, "OK"))
        self._track_background_task(reaction_task, name="add_reaction", msg_id=msg_id)
        self._ensure_running_card_started(msg_id)
        await self.bus.publish_inbound(inbound)

    @staticmethod
    def _parse_inbound_message(
        message_type: str,
        content: dict[str, Any],
        *,
        msg_id: str,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        normalized_type = (message_type or "text").lower()
        metadata: dict[str, Any] = {
            "message_type": normalized_type,
        }

        if normalized_type == "text":
            text = str(content.get("text", "")).strip()
            return text, [], metadata

        files: list[dict[str, Any]] = []
        if normalized_type == "image":
            image_key = str(content.get("image_key", "")).strip()
            metadata["image_key"] = image_key
            files.append(
                {
                    "filename": f"feishu-image-{msg_id}.png",
                    "size": 0,
                    "path": f"feishu://image/{image_key or msg_id}",
                    "status": "remote",
                    "source": "feishu",
                    "message_type": "image",
                    "image_key": image_key,
                }
            )
            text = "用户发送了一张飞书图片消息。当前系统已记录图片元数据；如需精确分析，请让用户补文字描述或把原图上传到 Web Workspace。"
            return text, files, metadata

        if normalized_type == "file":
            file_key = str(content.get("file_key", "")).strip()
            file_name = str(content.get("file_name", "")).strip() or f"feishu-file-{msg_id}"
            file_size = content.get("file_size", 0)
            try:
                size = int(file_size)
            except (TypeError, ValueError):
                size = 0
            metadata.update({"file_key": file_key, "file_name": file_name})
            files.append(
                {
                    "filename": Path(file_name).name,
                    "size": size,
                    "path": f"feishu://file/{file_key or msg_id}",
                    "status": "remote",
                    "source": "feishu",
                    "message_type": "file",
                    "file_key": file_key,
                }
            )
            text = f"用户发送了一个飞书文件：{Path(file_name).name}。当前系统已记录文件元数据；如需进一步分析，请让用户在 Web Workspace 上传原文件或补充说明。"
            return text, files, metadata

        if normalized_type in {"audio", "media"}:
            file_key = str(content.get("file_key", "")).strip()
            duration = content.get("duration", 0)
            try:
                size = int(duration)
            except (TypeError, ValueError):
                size = 0
            metadata.update({"file_key": file_key, "duration": duration})
            files.append(
                {
                    "filename": f"feishu-audio-{msg_id}.opus",
                    "size": size,
                    "path": f"feishu://audio/{file_key or msg_id}",
                    "status": "remote",
                    "source": "feishu",
                    "message_type": "audio",
                    "file_key": file_key,
                }
            )
            text = "用户发送了一条飞书语音消息。当前系统已记录语音元数据，但尚未接入自动转写；请先让用户补文字摘要，再给详细建议。"
            return text, files, metadata

        text = str(content.get("text", "")).strip()
        return text, files, metadata

    def _on_message(self, event) -> None:
        """Called by lark-oapi when a message is received (runs in lark thread)."""
        try:
            logger.info("[Feishu] raw event received: type=%s", type(event).__name__)
            message = event.event.message
            chat_id = message.chat_id
            msg_id = message.message_id
            message_type = getattr(message, "message_type", "text")
            sender_id = event.event.sender.sender_id.open_id

            # root_id is set when the message is a reply within a Feishu thread.
            # Use it as topic_id so all replies share the same DeerFlow thread.
            root_id = getattr(message, "root_id", None) or None

            # Parse message content
            content = json.loads(message.content)
            text, files, parsed_metadata = self._parse_inbound_message(
                message_type,
                content,
                msg_id=msg_id,
            )
            logger.info(
                "[Feishu] parsed message: chat_id=%s, msg_id=%s, root_id=%s, sender=%s, type=%s, text=%r",
                chat_id,
                msg_id,
                root_id,
                sender_id,
                message_type,
                text[:100] if text else "",
            )

            if not text:
                logger.info("[Feishu] empty/unsupported payload, ignoring message")
                return

            # Check if it's a command
            if text.startswith("/"):
                msg_type = InboundMessageType.COMMAND
            else:
                msg_type = InboundMessageType.CHAT

            # topic_id: use root_id for replies (same topic), msg_id for new messages (new topic)
            topic_id = root_id or msg_id

            inbound = self._make_inbound(
                chat_id=chat_id,
                user_id=sender_id,
                text=text,
                msg_type=msg_type,
                thread_ts=msg_id,
                files=files,
                metadata={"message_id": msg_id, "root_id": root_id, **parsed_metadata},
            )
            inbound.topic_id = topic_id

            # Schedule on the async event loop
            if self._main_loop and self._main_loop.is_running():
                logger.info("[Feishu] publishing inbound message to bus (type=%s, msg_id=%s)", msg_type.value, msg_id)
                fut = asyncio.run_coroutine_threadsafe(self._prepare_inbound(msg_id, inbound), self._main_loop)
                fut.add_done_callback(lambda f, mid=msg_id: self._log_future_error(f, "prepare_inbound", mid))
            else:
                logger.warning("[Feishu] main loop not running, cannot publish inbound message")
        except Exception:
            logger.exception("[Feishu] error processing message")
