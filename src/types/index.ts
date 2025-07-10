export * from './session';
export * from './dataset';
export * from './analysis';
export * from './model';
export * from './chat';
export * from './dataSources';

// Extend ChatMessage to allow optional suggestions
export type ChatMessageWithSuggestions = ChatMessage & { suggestions?: string[] }
