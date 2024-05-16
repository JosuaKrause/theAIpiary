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

import { URL_PREFIX } from '../misc/constants';
import { timeout } from '../misc/util';
import {
  ChatInitResponse,
  ChatPromptResponse,
  ChatRecoverResponse,
  ChatTextResponse,
  SessionId,
  TaskId,
} from './types';

export type ChatApiProvider = {
  response: (
    session: SessionId,
    task: TaskId,
    index: number,
  ) => Promise<ChatTextResponse>;
  new: () => Promise<ChatInitResponse>;
  recover: (session: SessionId) => Promise<ChatRecoverResponse>;
  prompt: (prompt: string, session: SessionId) => Promise<ChatPromptResponse>;
};

export const DEFAULT_CHAT_API: ChatApiProvider = {
  response: async (session, task, index) => {
    try {
      const res = await fetch(`${URL_PREFIX}/response`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session,
          task,
          index,
        }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      await timeout(500.0);
      return {
        diff: '',
        task,
        next_index: index,
      };
    }
  },
  new: async () => {
    const res = await fetch(`${URL_PREFIX}/new`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    return await res.json();
  },
  recover: async (session) => {
    try {
      const res = await fetch(`${URL_PREFIX}/recover`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session,
        }),
      });
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
      const res = await fetch(`${URL_PREFIX}/prompt`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session,
          prompt,
        }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        task: null,
      };
    }
  },
};
