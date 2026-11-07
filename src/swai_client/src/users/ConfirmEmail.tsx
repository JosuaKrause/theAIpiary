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
import { FormEventHandler, PureComponent } from 'react';
import styled from 'styled-components';
import { EmailChangeToken, UserEmail } from '../api/types';
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

const ConfirmEmailHeader = styled.h3`
  padding-left: 5px;
`;

const ConfirmEmailForm = styled.form`
  width: 100%;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

const ConfirmEmailElement = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  padding: 5px;
  margin: 5px;
  min-width: 21vw;
  min-height: 3em;
`;

const ConfirmEmailLink = styled.a`
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

  &:hover,
  &:focus {
    color: var(--main-text);
    background-color: var(--button-hover);
  }
  &:active {
    color: var(--main-text);
    background-color: var(--button-active);
  }
`;

const ConfirmEmailSubmit = styled.input`
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

type ConfirmEmailProps = {
  userActions: UserActions;
};
type ConfirmEmailState = {
  message: string | null;
  token: EmailChangeToken | null;
  newEmail: Readonly<UserEmail> | null;
  inFlight: boolean;
};

export default class ConfirmEmail extends PureComponent<
  ConfirmEmailProps,
  ConfirmEmailState
> {
  constructor(props: Readonly<ConfirmEmailProps>) {
    super(props);
    const params = new URL(window.location.href).searchParams;
    this.state = {
      message: null,
      token: params.get('token') as EmailChangeToken | null,
      newEmail: null,
      inFlight: false,
    };
  }

  handleSubmit: FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    const { token, inFlight } = this.state;
    if (!token || inFlight) {
      return;
    }
    const { userActions } = this.props;
    // NOTE: the change only happens on the button press, not when the link
    // is opened, so that a mail scanner following the link cannot use it
    this.setState({ inFlight: true, message: null }, () => {
      userActions
        .confirmEmailChange(token, (confirmed, email, message) => {
          this.setState({
            message,
            // NOTE: the link is used up either way
            token: null,
            newEmail: confirmed ? email : null,
          });
        })
        .catch((err) => {
          this.setState({
            message: `Something went wrong, try again later: ${err}`,
          });
        })
        .finally(() => {
          this.setState({ inFlight: false });
        });
    });
  };

  render() {
    const { message, token, newEmail, inFlight } = this.state;
    const loginHref = newEmail
      ? `/login?user=${encodeURIComponent(`${newEmail}`)}`
      : '/login';
    return (
      <VMain>
        <ConfirmEmailElement>
          <ConfirmEmailHeader>Confirm Email Change</ConfirmEmailHeader>
        </ConfirmEmailElement>
        {token ? (
          <ConfirmEmailForm onSubmit={this.handleSubmit}>
            <ConfirmEmailElement>
              Change the email of your account to the address this link was
              sent to? You will be logged out everywhere and log in with the
              new email and your current password.
            </ConfirmEmailElement>
            <ConfirmEmailElement>
              <ConfirmEmailLink href="/login">Cancel</ConfirmEmailLink>
              <ConfirmEmailSubmit
                type="submit"
                value="Confirm"
                disabled={inFlight}
              />
            </ConfirmEmailElement>
          </ConfirmEmailForm>
        ) : (
          <ConfirmEmailElement>
            {message ??
              'This page needs the link from the confirmation email.'}
          </ConfirmEmailElement>
        )}
        {token && message ? (
          <ConfirmEmailElement>{message}</ConfirmEmailElement>
        ) : null}
        {token ? null : (
          <ConfirmEmailElement>
            <ConfirmEmailLink href={loginHref}>Login</ConfirmEmailLink>
          </ConfirmEmailElement>
        )}
      </VMain>
    );
  }
} // ConfirmEmail
