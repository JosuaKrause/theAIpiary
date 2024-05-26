/**
 * Copyright (c) 2024 Josua Krause - All Rights Reserved
 *
 * THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
 * UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
 * THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
 *
 * The receipt or possession of the source code and/or any parts thereof does
 * not convey or imply any right to use them for any purpose other than the
 * purpose for which they were provided to you.
 *
 * The software is provided "AS IS", without warranty of any kind, express or
 * implied, including but not limited to the warranties of merchantability,
 * fitness for a particular purpose and non infringement. In no event shall the
 * authors or copyright holders be liable for any claim, damages or other
 * liability, whether in an action of contract, tort or otherwise, arising
 * from, out of or in connection with the software or the use or other dealings
 * in the software.
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the software.
 */
import { ChatApiProvider, DEFAULT_CHAT_API } from '../api/chat';
import { Message, SessionId, TaskId } from '../api/types';

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
    setThinking: (isThinking: boolean) => void,
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
    setThinking: (isThinking: boolean) => void,
    appendMessage: (msg: Readonly<Message>) => void,
  ) {
    let index = 0;
    setThinking(true);

    for (;;) {
      this.responseNum += 1;
      const responseNum = this.responseNum;
      const { diff, nextTask, nextIndex } = await this.api.response(
        session,
        task,
        index,
      );
      if (responseNum !== this.responseNum) {
        break;
      }
      if (diff) {
        appendMessage({ role: 'assistant', content: diff });
      }
      if (nextIndex === undefined || !nextTask) {
        setThinking(false);
        break;
      }
      index = nextIndex;
      task = nextTask;
    }
  }

  async sendMessage(
    session: Readonly<SessionId>,
    prompt: Readonly<string>,
    setThinking: (isThinking: boolean) => void,
    appendMessage: (msg: Readonly<Message>) => void,
  ) {
    if (!prompt) {
      return;
    }
    appendMessage({ role: 'user', content: prompt });
    const { task } = await this.api.prompt(prompt, session);
    if (task) {
      await this.readResponse(session, task, setThinking, appendMessage);
    } else {
      appendMessage({ role: 'assistant', content: 'ERROR!' });
    }
  }
} // ChatActions
