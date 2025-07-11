import type { InjectionKey } from 'vue';

export const sessionNameUpdatedKey = Symbol() as InjectionKey<() => void>;
