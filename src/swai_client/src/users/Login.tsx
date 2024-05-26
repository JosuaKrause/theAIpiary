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
import React, { FormEventHandler, PureComponent } from 'react';
import styled from 'styled-components';
import { Password, UserName } from '../api/types';
import UserActions from './UserActions';

const VMain = styled.div`
  display: flex;
  justify-content: center;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 60vw;
  width: fit-content;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    max-width: 100vw;
  }
`;

const LoginForm = styled.form`
  width: fit-content;
`;

const LoginElement = styled.div`
  padding: 5px;
  margin: 5px;
  clear: both;
  width: fit-content;
`;

const LoginLabel = styled.label`
  float: left;
`;

const LoginInputText = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  padding: var(--item-padding);
  float: right;
`;

const LoginSubmit = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  padding: var(--item-padding);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);
  float: right;

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

type LoginProps = {
  userActions: UserActions;
};
type EmptyLoginProps = {
  userActions: null;
};
type LoginState = {
  message: string | null;
};

export default class Login extends PureComponent<
  Readonly<LoginProps>,
  Readonly<LoginState>
> {
  private readonly nameRef: React.RefObject<HTMLInputElement>;
  private readonly passwordRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<LoginProps>) {
    super(props);
    this.state = { message: null };
    this.nameRef = React.createRef();
    this.passwordRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate({ userActions: null }, { message: null });
  }

  componentDidUpdate(
    _prevProps: Readonly<LoginProps> | EmptyLoginProps,
    _prevState: Readonly<LoginState>,
  ) {
    const nameInput = this.nameRef.current;
    if (nameInput) {
      const params = new URL(window.location.href).searchParams;
      const user = params.get('user');
      if (user) {
        nameInput.value = user;
        const newParams = new URLSearchParams(params);
        newParams.delete('user');
        const url = new URL(window.location.href);
        url.search = newParams.toString();
        history.replaceState(history.state, '', url);
      }
    }
  }

  handleSubmit: FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    const nameInput = this.nameRef.current;
    const passwordInput = this.passwordRef.current;
    if (!nameInput || !passwordInput) {
      return;
    }
    const userName = nameInput.value as UserName;
    const password = passwordInput.value as Password;
    const { userActions } = this.props;
    userActions.login(userName, password, (user) => {
      if (user.name) {
        window.location.href = '/profile';
      } else {
        this.setState({
          message: user.message,
        });
      }
    });
  };

  render() {
    const { message } = this.state;
    return (
      <VMain>
        <LoginForm onSubmit={this.handleSubmit}>
          <LoginElement>
            <LoginLabel htmlFor="username">Email:</LoginLabel>
            <LoginInputText
              autoComplete="username"
              name="username"
              type="text"
              ref={this.nameRef}
            />
          </LoginElement>
          <LoginElement>
            <LoginLabel htmlFor="password">Password:</LoginLabel>
            <LoginInputText
              autoComplete="password"
              name="password"
              type="password"
              ref={this.passwordRef}
            />
          </LoginElement>
          <LoginElement>
            <LoginSubmit
              type="submit"
              value="Login"
            />
          </LoginElement>
        </LoginForm>
        {message ? <LoginElement>{message}</LoginElement> : null}
      </VMain>
    );
  }
} // Login
