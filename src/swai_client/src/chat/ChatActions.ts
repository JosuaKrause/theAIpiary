/**
 * Copyright (C) 2024 Josua Krause
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { ChatApiProvider, DEFAULT_CHAT_API } from '../api/chat';
import { Message, SessionId, TaskId, Thinking } from '../api/types';

export default class ChatActions {
  private readonly api: ChatApiProvider;

  private responseNum: number;

  constructor(api?: ChatApiProvider) {
    this.api = api ?? DEFAULT_CHAT_API;
    this.responseNum = 0;
  }

  async doInit(
    session: Readonly<SessionId> | undefined,
    setMessages: (messages: Readonly<Message[]>) => void,
    setSession: (session: Readonly<SessionId>) => void,
    setThinking: (thinking: Thinking) => void,
    appendMessage: (msg: Readonly<Message>) => void,
  ) {
    this.responseNum = 0;
    let task = undefined;
    if (!session) {
      const { session: newSession, messages } = await this.api.new();
      setSession(newSession);
      setMessages(messages);
      session = newSession;
    } else {
      const { messages, task: newTask } = await this.api.recover(session);
      setMessages(messages);
      task = newTask;
    }
    if (session && task) {
      await this.readResponse(session, task, setThinking, appendMessage);
    }
  }

  async readResponse(
    session: Readonly<SessionId>,
    task: Readonly<TaskId>,
    setThinking: (thinking: Thinking) => void,
    appendMessage: (msg: Readonly<Message>) => void,
  ) {
    let index = 0;
    setThinking('thinking');

    for (;;) {
      this.responseNum += 1;
      const responseNum = this.responseNum;
      const { diff, nextTask, nextIndex, status } = await this.api.response(
        session,
        task,
        index,
      );
      if (status === 'error') {
        setThinking('error');
      } else if (status === 'wait') {
        setThinking('queued');
      } else {
        setThinking('thinking');
      }
      if (responseNum !== this.responseNum) {
        break;
      }
      if (diff) {
        appendMessage({ role: 'assistant', content: diff });
      }
      if (nextIndex === undefined || !nextTask) {
        if (status !== 'error') {
          setThinking('inactive');
        }
        break;
      }
      index = nextIndex;
      task = nextTask;
    }
  }

  async sendMessage(
    session: Readonly<SessionId>,
    prompt: Readonly<string>,
    setThinking: (thinking: Thinking) => void,
    appendMessage: (msg: Readonly<Message>) => void,
  ) {
    const response = await this.api.prompt(prompt, session);
    const { error } = response;
    if (error) {
      const { message } = response;
      appendMessage({
        role: 'assistant',
        content: `\n\n**[ERROR]** ${message}`,
      });
      setThinking('error');
    } else {
      const { task } = response;
      if (task) {
        appendMessage({ role: 'user', content: prompt });
        await this.readResponse(session, task, setThinking, appendMessage);
      } else {
        setThinking('inactive');
      }
    }
  }
} // ChatActions
