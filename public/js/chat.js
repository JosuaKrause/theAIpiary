// @ts-check
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
 * liability, whether in an action of contract, tort or otherwise, arising from,
 * out of or in connection with the software or the use or other dealings in the
 * software.
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the software.
 */
import { marked } from '../lib/marked.esm.js';
import DOMPurify from '../lib/purify.es.mjs';
import { getElement } from './util.js';

/**
 * @typedef {'assistant' | 'user'} Role
 */

/**
 * @typedef {{
 *  role: Role;
 *  content: string;
 * }} Message
 */

/**
 * @typedef {{
 *  session: string;
 *  messages: Message[];
 * }} ChatInitResponse
 */

/**
 * @typedef {{
 *  messages: Message[];
 *  task: string?;
 * }} ChatRecoverResponse
 */

/**
 * @typedef {{
 *  task: string?;
 * }} ChatPromptResponse
 */

/**
 * @typedef {{
 *  diff: string;
 *  task: string?;
 *  next_index: number?;
 * }} ChatTextResponse
 */

/**
 * @typedef {{
 *   session: string?;
 * }} ChatState
 */

export default class Chat {
  constructor(
    /** @type {string} */ inputbarId,
    /** @type {string} */ responseId,
    /** @type {string} */ base,
  ) {
    /** @type {HTMLTextAreaElement} */ this._inputbar = getElement(inputbarId);
    /** @type {HTMLDivElement} */ this._response = getElement(responseId);
    /** @type {string} */ this._base = base;
    /** @type {string} */ this._input = '';
    /** @type {string?} */ this._session = null;
    /** @type {string?} */ this._task = null;
    /** @type {number?} */ this._index = null;
    /** @type {number} */ this._response_num = 0;
    /** @type {string} */ this._cur_msg = '';
    /** @type {ChatState} */ this._state = {
      session: this._session,
    };
    window.addEventListener('popstate', (event) => {
      /** @type {ChatState} */ const state = event.state;
      const { session } = state;
      const oldSession = this._session;
      this._session = session;
      this._state = {
        session: this._session,
      };
      if (oldSession !== session) {
        this._task = null;
        this._index = null;
        this._input = '';
        this._inputbar.value = this._input;
      }
      this.initView();
    });

    this.getFromParams();
    this.setupInput();
  }

  getFromParams() {
    const params = new URL(window.location.href).searchParams;
    const session = params.get('session');
    if (session) {
      this._session = session;
    }
    this._state = {
      session: this._session,
    };
  }

  pushHistory() {
    const { session: oldSession } = this._state;
    const session = this._session;
    if (oldSession !== session) {
      const history = window.history;
      const params = new URLSearchParams();
      if (session) {
        params.set('session', session);
      }
      const url = new URL(window.location.href);
      url.search = params.toString();
      history.pushState({ session }, '', url);
      this._state = {
        session,
      };
    }
  }

  setupInput() {
    const inputbar = this._inputbar;
    inputbar.addEventListener('keydown', async (e) => {
      if (e.defaultPrevented) {
        return;
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (inputbar.value === this._input) {
          return;
        }
        this._input = inputbar.value;
        await this.sendMessage();
      }
    });
  }

  initView() {
    setTimeout(async () => {
      await this.doInit();
    }, 0);
  }

  async doInit() {
    this._response_num = 0;
    if (!this._session) {
      const { session, messages } = await this.getChatInit();
      this._session = session;
      this._task = null;
      this._index = null;
      this.pushHistory();
      this.renderMessages(messages);
    } else {
      const { messages, task } = await this.getChatRecover();
      this.renderMessages(messages);
      this._task = task;
      this._index = 0;
    }
    this.readResponse();
  }

  readResponse() {
    const readNext = async () => {
      if (!this._task) {
        this._response.classList.remove('thinking');
        return;
      }
      this._response_num += 1;
      const response_num = this._response_num;
      this._response.classList.add('thinking');
      const {
        diff,
        task,
        next_index: nextIndex,
      } = await this.getChatResponse();
      if (response_num !== this._response_num) {
        return;
      }
      if (diff) {
        this.appendMessage(diff, 'assistant');
      }
      this._index = nextIndex;
      this._task = task;
      await readNext();
    };

    setTimeout(readNext, 0);
  }

  async sendMessage() {
    const prompt = this._input;
    if (!prompt) {
      return;
    }
    this._input = '';
    this._inputbar.value = '';
    this.appendMessage(prompt, 'user');
    const { task } = await this.getChatPrompt(prompt);
    this._task = task;
    this._index = 0;
    if (task) {
      this.readResponse();
    } else {
      this.appendMessage('ERROR!', 'assistant');
    }
  }

  /** @type {() => Promise<ChatInitResponse>} */
  async getChatInit() {
    const res = await fetch(`${this._base}/api/new`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    return await res.json();
  }

  /** @type {() => Promise<ChatRecoverResponse>} */
  async getChatRecover() {
    try {
      const res = await fetch(`${this._base}/api/recover`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session: this._session,
        }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        messages: [],
        task: null,
      };
    }
  }

  /** @type {(prompt: string) => Promise<ChatPromptResponse>} */
  async getChatPrompt(prompt) {
    try {
      const res = await fetch(`${this._base}/api/prompt`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session: this._session,
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
  }

  /** @type {() => Promise<ChatTextResponse>} */
  async getChatResponse() {
    try {
      const res = await fetch(`${this._base}/api/response`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session: this._session,
          task: this._task,
          index: this._index,
        }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        diff: '[ERROR]',
        task: null,
        next_index: null,
      };
    }
  }

  renderMessages(/** @type {Message[]} */ messages) {
    this._response.replaceChildren();
    messages
      .filter(({ content }) => content)
      .forEach(({ content, role }) => {
        this.appendMessage(content, role);
      });
  }

  appendMessage(/** @type {string} */ message, /** @type {Role} */ role) {
    const roleMap = {
      user: 'response-user',
      assistant: 'response-assistant',
    };
    const className = roleMap[role];
    const last = this._response.firstElementChild;
    let current;
    if (last && last.classList.contains(className)) {
      current = last;
    } else {
      const textElement = document.createElement('div');
      textElement.classList.add(`${className}-message`);
      textElement.classList.add('response-message');
      const element = document.createElement('div');
      element.classList.add(className);
      element.classList.add('response-parent');
      element.appendChild(textElement);
      if (last) {
        this._response.insertBefore(element, last);
      } else {
        this._response.appendChild(element);
      }
      current = element;
      this._cur_msg = '';
    }
    this._cur_msg += message;
    const textBody = current.firstElementChild;
    if (textBody) {
      textBody.innerHTML = DOMPurify.sanitize(marked.parse(this._cur_msg));
    }
  }
} // Chat
