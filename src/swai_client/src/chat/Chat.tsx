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
import React, { PureComponent, ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import { SpecialComponents } from 'react-markdown/lib/ast-to-react';
import { NormalComponents } from 'react-markdown/lib/complex-types';
import { ConnectedProps, connect } from 'react-redux';
import styled, { css } from 'styled-components';
import {
  ACTIVE_THINKING,
  Message,
  Role,
  SessionId,
  Thinking,
} from '../api/types';
import { RootState } from '../store';
import ChatActions from './ChatActions';
import { setSession } from './ChatStateSlice';

const VMain = styled.div`
  display: flex;
  justify-content: end;
  flex-direction: column;
  flex-grow: 1;
  max-width: 60vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    max-width: 100%;
    height: 100%;
    max-height: 100%;
  }
`;

type ResponseProps = {
  thinking: Thinking;
};

function styleResponse(thinking: Thinking) {
  if (thinking === 'inactive') {
    return css``;
  }
  if (thinking === 'queued') {
    return css`
      &:before {
        display: block;
        font-weight: 500;
        content: 'queued';
        width: 100%;
        float: right;
        clear: both;
        text-align: right;
      }
    `;
  }
  if (thinking === 'error') {
    return css`
      &:before {
        display: block;
        font-weight: 500;
        content: 'error';
        width: 100%;
        float: right;
        clear: both;
        text-align: right;
      }
    `;
  }
  return css`
    &:before {
      display: block;
      font-weight: 500;
      animation: ellipsis steps(4, end) 900ms infinite;
      content: '\\2026';
      width: 100%;
      float: right;
      clear: both;
      text-align: right;
      translate: -5px 0;
    }
  `;
}

const Response = styled.div<ResponseProps>`
  overflow: auto;
  flex-grow: 0;
  display: flex;
  flex-direction: column-reverse;

  @media (hover: none) and (max-width: 480px) {
    width: calc(100vw - 5px);
    flex-grow: 1;
    padding-top: 65px;
  }

  ${({ thinking }) => styleResponse(thinking)}
`;

type ResponseElemProps = {
  role: Role;
};

function styleResponseElem(role: Role) {
  switch (role) {
    case 'user':
      return css`
        float: left;
        align-self: flex-start;
        width: fit-content;
        max-width: 90%;
      `;
    case 'assistant':
      return css`
        float: right;
        align-self: flex-end;
        width: 90%;
      `;
  }
}

const ResponseElem = styled.div<ResponseElemProps>`
  width: 100%;
  height: max-content;
  clear: both;
  ${({ role }) => styleResponseElem(role)}
`;

type ResponseMessageProps = {
  role: Role;
};

function styleResponseMessage(role: Role) {
  switch (role) {
    case 'user':
      return css`
        text-align: left;
        color: black;
        background-color: blanchedalmond;
        border: 1px solid darkgoldenrod;
        border-bottom-left-radius: 0;
      `;
    case 'assistant':
      return css`
        text-align: left;
        color: black;
        background-color: lightskyblue;
        border: 1px solid cornflowerblue;
        border-bottom-right-radius: 0;
      `;
  }
}

const ResponseMessage = styled.div<ResponseMessageProps>`
  border-radius: 12px;
  padding: 12px;
  margin: 3px;
  ${({ role }) => styleResponseMessage(role)}
`;

const InputBar = styled.div`
  flex-shrink: 0;
  flex-grow: 0;
  margin: 3px;
  display: flex;
  flex-direction: row;
  justify-content: space-between;

  @media (hover: none) and (max-width: 480px) {
    width: calc(100vw - 5px);
    height: auto;
  }
`;

const SendButton = styled.input`
  appearance: none;
  border-radius: var(--item-padding);
  padding: 0 var(--item-padding);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);
  flex-grow: 0;
  height: 3.5em;
  vertical-align: middle;
  align-self: center;

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

const InputText = styled.textarea`
  border-radius: 12px;
  padding: 12px;
  border-bottom-left-radius: 0;
  width: 90%;
  outline: none;
  min-height: 6em;
  max-height: 30vh;
  resize: vertical;

  @media (hover: none) and (max-width: 480px) {
    max-height: 30%;
  }
`;

const Link = styled.a`
  color: var(--md-anchor);

  &:visited {
    color: var(--md-anchor);
  }
  &:active {
    color: var(--md-anchor);
  }
  &:hover {
    color: var(--md-anchor-hover);
  }
`;

interface ChatProps extends ConnectChat {
  chatActions: ChatActions;
  ready: boolean;
}

type EmptyChatProps = {
  session: undefined;
  ready: false;
};

type ChatState = {
  messages: Readonly<Message[]>;
  thinking: Thinking;
};

const MD_COMPONENTS: Partial<
  Omit<NormalComponents, keyof SpecialComponents> & SpecialComponents
> = {
  a: ({ node: _, ...props }) => <Link {...props} />,
};

class Chat extends PureComponent<ChatProps, ChatState> {
  private readonly inputRef: React.RefObject<HTMLTextAreaElement>;

  constructor(props: Readonly<ChatProps>) {
    super(props);
    this.state = {
      messages: [],
      thinking: 'inactive',
    };
    this.inputRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate({ session: undefined, ready: false }, undefined);
  }

  componentDidUpdate(
    prevProps: Readonly<ChatProps> | EmptyChatProps,
    _prevState: Readonly<ChatState> | undefined,
  ): void {
    const { ready, session, chatActions } = this.props;
    const { session: prevSession, ready: prevReady } = prevProps;
    if (!ready) {
      return;
    }
    if (ready && ready !== prevReady) {
      chatActions
        .doInit(
          session,
          this.setMessages,
          this.setSession,
          this.setThinking,
          this.appendMessage,
        )
        .catch((err) => {
          console.error(err);
        });
    }
    if (session && session !== prevSession && prevSession !== undefined) {
      chatActions
        .doInit(
          session,
          this.setMessages,
          this.setSession,
          this.setThinking,
          this.appendMessage,
        )
        .catch((err) => {
          console.error(err);
        });
    }
  }

  setMessages = (messages: Readonly<Message[]>) => {
    this.setState({
      messages,
    });
  };

  setSession = (session: Readonly<SessionId>) => {
    const { dispatch } = this.props;
    dispatch(setSession({ session }));
  };

  setThinking = (thinking: Thinking) => {
    this.setState({ thinking });
  };

  appendMessage = (msg: Readonly<Message>) => {
    const { messages } = this.state;
    if (!messages.length) {
      this.setState({ messages: [msg] });
      return;
    }
    const last = messages[messages.length - 1];
    if (last.role === msg.role) {
      this.setState({
        messages: [
          ...messages.slice(0, -1),
          {
            role: last.role,
            content: `${last.content}${msg.content}`,
          },
        ],
      });
    } else {
      this.setState({
        messages: [...messages, msg],
      });
    }
  };

  onSend: React.MouseEventHandler<HTMLInputElement> = async (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    await this.doSend(true);
  };

  onTextKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = async (
    e,
  ) => {
    if (e.defaultPrevented) {
      return;
    }
    if (e.key !== 'Enter' || e.shiftKey) {
      return;
    }
    e.preventDefault();
    await this.doSend(false);
  };

  async doSend(viaClick: boolean) {
    const inputText = this.inputRef.current;
    if (inputText === null) {
      return;
    }
    const { chatActions, session } = this.props;
    const prompt = inputText.value;
    if (!session) {
      return;
    }
    const { thinking } = this.state;
    if (!prompt && (!viaClick || !ACTIVE_THINKING.includes(thinking))) {
      return;
    }
    let first = true;
    await chatActions.sendMessage(session, prompt, this.setThinking, (msg) => {
      this.appendMessage(msg);
      if (first) {
        inputText.value = '';
        first = false;
      }
    });
  }

  render(): ReactNode {
    const { messages, thinking } = this.state;
    const revMessages = [...messages].reverse();
    return (
      <VMain>
        <Response thinking={thinking}>
          {revMessages.map(({ role, content }, ix) => (
            <ResponseElem
              key={messages.length - ix - 1}
              role={role}>
              <ResponseMessage role={role}>
                <ReactMarkdown
                  skipHtml={true}
                  components={MD_COMPONENTS}>
                  {content}
                </ReactMarkdown>
              </ResponseMessage>
            </ResponseElem>
          ))}
        </Response>
        <InputBar>
          <InputText
            ref={this.inputRef}
            onKeyDown={this.onTextKeyDown}
            rows={3}
            dir=""
            autoCapitalize="off"
            autoComplete="off"
            aria-autocomplete="both"
            spellCheck={false}
            aria-label="Type your message..."
            autoCorrect="off"
            placeholder="Type your message..."
            autoFocus={false}></InputText>
          <SendButton
            type="button"
            value={ACTIVE_THINKING.includes(thinking) ? 'Stop' : 'Send'}
            onClick={this.onSend}
          />
        </InputBar>
      </VMain>
    );
  }
} // Chat

const connector = connect((state: RootState) => ({
  session: state.chatState.currentSession,
}));

export default connector(Chat);

type ConnectChat = ConnectedProps<typeof connector>;
