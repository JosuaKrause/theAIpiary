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
import { Password, ResetToken, UserEmail } from '../api/types';
import UserActions from './UserActions';

const VMain = styled.div`
  display: flex;
  justify-content: center;
  flex-direction: column;
  max-width: 60vw;
  width: fit-content;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    max-width: 100vw;
    width: 100vw;
  }
`;

const ResetPasswordHeader = styled.h3`
  padding-left: 5px;
`;

const ResetPasswordForm = styled.form`
  width: 100%;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

const ResetPasswordElement = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  padding: 5px;
  margin: 5px;
  min-width: 21vw;
  min-height: 3em;
`;

const ResetPasswordLink = styled.a`
  text-decoration: none;
  border-radius: calc(var(--item-padding) * 0.5);
  padding: calc(var(--item-padding) * 0.5);
  margin: calc(var(--item-padding) * 0.5);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);
  flex-grow: 0;

  &:visited {
    color: var(--main-text);
    background-color: var(--button-background);
  }

  &:hover {
    color: var(--main-text);
    background-color: var(--button-hover);
  }
  &:active {
    color: var(--main-text);
    background-color: var(--button-active);
  }
`;

const ResetPasswordLabel = styled.label`
  flex-grow: 0;
  padding: 5px;
`;

const ResetPasswordInputText = styled.input`
  appearance: none;
  padding: var(--item-padding);
  flex-grow: 0;
  padding: 5px;
  margin: 2px;
`;

const ResetPasswordSubmit = styled.input`
  appearance: none;
  border-radius: calc(var(--item-padding) * 0.5);
  padding: calc(var(--item-padding) * 0.5);
  margin: calc(var(--item-padding) * 0.5);
  cursor: pointer;
  color: var(--main-text);
  background-color: var(--button-background);
  flex-grow: 0;

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
type ResetPasswordState = {
  message: string | null;
  resetToken: ResetToken | undefined;
  inFlightCreateResetToken: boolean;
};

export default class ResetPassword extends PureComponent<
  ResetPasswordProps,
  ResetPasswordState
> {
  private readonly nameRef: React.RefObject<HTMLInputElement>;
  private readonly newPasswordRef: React.RefObject<HTMLInputElement>;
  private readonly confirmPasswordRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<ResetPasswordProps>) {
    super(props);
    this.state = {
      message: null,
      resetToken: undefined,
      inFlightCreateResetToken: false,
    };
    this.nameRef = React.createRef();
    this.newPasswordRef = React.createRef();
    this.confirmPasswordRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate(undefined, {
      message: null,
      resetToken: undefined,
      inFlightCreateResetToken: false,
    });
  }

  componentDidUpdate(
    _prevProps: Readonly<ResetPasswordProps> | undefined,
    _prevState: Readonly<ResetPasswordState>,
  ) {
    const { resetToken } = this.state;
    const params = new URL(window.location.href).searchParams;
    const paramResetToken = params.get('token') as ResetToken | undefined;
    if (!resetToken && paramResetToken) {
      this.setState({
        resetToken: paramResetToken,
      });
    }
  }

  handleResetTokenSubmit: FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    const { resetToken } = this.state;
    if (!resetToken) {
      this.setState({
        message: 'No reset token set!',
      });
      return;
    }
    const newPasswordInput = this.newPasswordRef.current;
    const confirmPasswordInput = this.confirmPasswordRef.current;
    if (!newPasswordInput || !confirmPasswordInput) {
      return;
    }
    const newPassword = newPasswordInput.value as Password;
    const confirmPassword = confirmPasswordInput.value as Password;
    if (
      !newPassword ||
      !newPassword.length ||
      !confirmPassword ||
      !confirmPassword.length
    ) {
      this.setState({
        message: 'Please provide your new password in both fields!',
      });
      return;
    }
    if (newPassword !== confirmPassword) {
      this.setState({
        message: 'The entered passwords do not match!',
      });
      return;
    }
    const { userActions } = this.props;
    userActions.changePassword(resetToken, newPassword, (user) => {
      if (user.logged) {
        window.location.href = `/login?user=${user.email}`;
      } else {
        this.setState({
          message: user.message,
        });
      }
    });
  };

  handleCreateResetTokenSubmit: FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    const { resetToken, inFlightCreateResetToken } = this.state;
    if (resetToken) {
      this.setState({
        message: 'Reset token already set!',
      });
      return;
    }
    const nameInput = this.nameRef.current;
    if (!nameInput) {
      return;
    }
    const name = nameInput.value as UserEmail;
    if (!name || !name.length) {
      this.setState({
        message: 'Please provide your email!',
      });
      return;
    }
    if (inFlightCreateResetToken) {
      this.setState({
        message: "Clicking the button multiple times won't make it go faster!",
      });
      return;
    }
    const { userActions } = this.props;
    this.setState(
      {
        inFlightCreateResetToken: true,
      },
      () => {
        userActions.resetPassword(name, (email) => {
          if (email) {
            this.setState({
              message: `Instructions sent to ${email}!`,
            });
            nameInput.value = '';
          } else {
            this.setState({
              message: `Incorrect email or try again in a few minutes!`,
            });
          }
          this.setState({
            inFlightCreateResetToken: false,
          });
        });
      },
    );
  };

  render() {
    const { message, resetToken } = this.state;
    return (
      <VMain>
        <ResetPasswordElement>
          <ResetPasswordHeader>Reset Password</ResetPasswordHeader>
        </ResetPasswordElement>
        {resetToken ? (
          <ResetPasswordForm onSubmit={this.handleResetTokenSubmit}>
            <ResetPasswordElement>
              <ResetPasswordLabel htmlFor="new-password">
                New Password:
              </ResetPasswordLabel>
              <ResetPasswordInputText
                autoComplete="new-password"
                name="new-password"
                type="password"
                ref={this.newPasswordRef}
              />
            </ResetPasswordElement>
            <ResetPasswordElement>
              <ResetPasswordLabel htmlFor="confirm-password">
                Confirm Password:
              </ResetPasswordLabel>
              <ResetPasswordInputText
                autoComplete="new-password"
                name="confirm-password"
                type="password"
                ref={this.confirmPasswordRef}
              />
            </ResetPasswordElement>
            <ResetPasswordElement>
              <ResetPasswordSubmit
                type="submit"
                value="Change Password"
              />
            </ResetPasswordElement>
          </ResetPasswordForm>
        ) : (
          <ResetPasswordForm onSubmit={this.handleCreateResetTokenSubmit}>
            <ResetPasswordElement>
              <ResetPasswordLabel htmlFor="username">
                Email:
              </ResetPasswordLabel>
              <ResetPasswordInputText
                autoComplete="username"
                name="username"
                type="text"
                ref={this.nameRef}
              />
            </ResetPasswordElement>
            <ResetPasswordElement>
              <ResetPasswordLink href="/login">Back</ResetPasswordLink>
              <ResetPasswordSubmit
                type="submit"
                value="Send Email"
              />
            </ResetPasswordElement>
          </ResetPasswordForm>
        )}
        <ResetPasswordElement>{message}</ResetPasswordElement>
      </VMain>
    );
  }
} // ResetPassword
