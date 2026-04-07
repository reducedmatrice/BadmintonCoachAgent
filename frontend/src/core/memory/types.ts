export interface UserMemory {
  version: string;
  lastUpdated: string;
  user: {
    workContext: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
    personalContext: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
    topOfMind: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
  };
  history: {
    recentMonths: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
    earlierContext: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
    longTermBackground: {
      summary: string;
      updatedAt: string;
      sources: string[];
      thread_ids: string[];
    };
  };
  facts: {
    id: string;
    content: string;
    category: string;
    confidence: number;
    createdAt: string;
    source: string;
    sources: string[];
    thread_ids: string[];
  }[];
}
