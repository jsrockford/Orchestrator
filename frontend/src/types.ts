export type DiscussionState = 'idle' | 'running' | 'paused';

export interface DiscussionSettings {
  maxTurns: number;
  startingModel: string;
  discussionTopic: string;
  includeHistory: boolean;
  logLevel: string;
}
