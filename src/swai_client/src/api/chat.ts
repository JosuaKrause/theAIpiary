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
import { URL_PREFIX } from '../misc/constants';
import { timeout } from '../misc/util';
import {
  ApiChatInitResponse,
  ApiChatPromptResponse,
  ApiChatTextResponse,
  ChatInitResponse,
  ChatPromptResponse,
  ChatRecoverResponse,
  ChatTextResponse,
  SessionId,
  TaskId,
  checkResponse,
} from './types';

export type ChatApiProvider = {
  response: (
    session: Readonly<SessionId>,
    task: Readonly<TaskId>,
    index: number,
  ) => Promise<ChatTextResponse>;
  new: () => Promise<ChatInitResponse>;
  recover: (session: Readonly<SessionId>) => Promise<ChatRecoverResponse>;
  prompt: (
    prompt: Readonly<string>,
    session: Readonly<SessionId>,
  ) => Promise<ChatPromptResponse>;
};

export const DEFAULT_CHAT_API: ChatApiProvider = {
  response: async (session, task, index) => {
    try {
      const res = await fetch(`${URL_PREFIX}/chat/response`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_session: session,
          task,
          index,
        }),
      });
      checkResponse(res);
      const {
        diff,
        task: nextTask,
        next_index: nextIndex,
        status,
      } = (await res.json()) as ApiChatTextResponse;
      return {
        diff,
        nextTask,
        nextIndex,
        status,
      };
    } catch (err) {
      console.error(err);
      await timeout(500.0);
      return {
        diff: '',
        nextTask: task,
        nextIndex: index,
        status: 'unknown',
      };
    }
  },
  new: async () => {
    const res = await fetch(`${URL_PREFIX}/chat/new`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    checkResponse(res);
    const { model_session, messages } =
      (await res.json()) as ApiChatInitResponse;
    return {
      session: model_session,
      messages,
    };
  },
  recover: async (session) => {
    try {
      const res = await fetch(`${URL_PREFIX}/chat/recover`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_session: session,
        }),
      });
      checkResponse(res);
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        name: 'ERROR',
        messages: [],
        task: null,
      };
    }
  },
  prompt: async (prompt, session) => {
    try {
      const res = await fetch(`${URL_PREFIX}/chat/prompt`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_session: session,
          prompt,
        }),
      });
      checkResponse(res);
      const { task, status } = (await res.json()) as ApiChatPromptResponse;
      return {
        error: false,
        task,
        status,
      };
    } catch (err) {
      console.error(err);
      return {
        error: true,
        message: 'see logs for details...',
      };
    }
  },
};
