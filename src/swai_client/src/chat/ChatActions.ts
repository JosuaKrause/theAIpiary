import { ChatApiProvider, DEFAULT_CHAT_API } from '../api/chat';

export default class ChatActions {
  private readonly api: ChatApiProvider;

  constructor(api?: ChatApiProvider) {
    this.api = api ?? DEFAULT_CHAT_API;
  }
} // ChatActions
