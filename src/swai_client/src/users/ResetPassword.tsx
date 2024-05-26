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
import { Password, ResetToken } from '../api/types';
import UserActions from './UserActions';

const VMain = styled.div`
  display: flex;
  justify-content: center;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 60vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
  }
`;

const ResetPasswordInputText = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  padding: var(--item-padding);
  border-right-style: none;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
`;

const ResetPasswordSubmit = styled.input`
  appearance: none;
  border-radius: var(--item-radius);
  border-left-style: none;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  padding: var(--item-padding);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);

  &:hover {
    background-color: var(--button-hover);
  }
  &:active {
    background-color: var(--button-active);
  }
`;

type ResetPasswordProps = {
  userActions: UserActions;
};
type ResetPasswordState = Record<string, void>;

export default class ResetPassword extends PureComponent<
  ResetPasswordProps,
  ResetPasswordState
> {
  private readonly newPasswordRef: React.RefObject<HTMLInputElement>;
  private readonly confirmPasswordRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<ResetPasswordProps>) {
    super(props);
    this.state = {};
    this.newPasswordRef = React.createRef();
    this.confirmPasswordRef = React.createRef();
  }

  handleSubmit: FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    const params = new URL(window.location.href).searchParams;
    const resetToken = params.get('token') as ResetToken | undefined;
    if (!resetToken) {
      return;
    }
    const newPasswordInput = this.newPasswordRef.current;
    const confirmPasswordInput = this.confirmPasswordRef.current;
    if (!newPasswordInput || !confirmPasswordInput) {
      return;
    }
    const newPassword = newPasswordInput.value as Password;
    const confirmPassword = confirmPasswordInput.value as Password;
    if (newPassword !== confirmPassword) {
      return;
    }
    const { userActions } = this.props;
    userActions.changePassword(resetToken, newPassword, (user) => {
      if (user) {
        window.location.href = `/login?user=${user.name}`;
      }
    });
  };

  render() {
    return (
      <VMain>
        <form onSubmit={this.handleSubmit}>
          <label>
            New Password:&nbsp;
            <ResetPasswordInputText
              autoComplete="new-password"
              name="new-password"
              type="password"
              ref={this.newPasswordRef}
            />
          </label>
          <label>
            Confirm Password:&nbsp;
            <ResetPasswordInputText
              autoComplete="new-password"
              name="confirm-password"
              type="password"
              ref={this.confirmPasswordRef}
            />
          </label>
          <ResetPasswordSubmit
            type="submit"
            value="Login"
          />
        </form>
      </VMain>
    );
  }
} // ResetPassword
