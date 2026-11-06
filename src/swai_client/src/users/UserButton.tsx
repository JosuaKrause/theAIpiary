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
import React, { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { DisplayName } from '../api/types';
import { redirectLogin } from '../misc/common';
import { RootState } from '../store';
import UserActions from './UserActions';
import { setUser } from './UserStateSlice';

const Circle = styled.div`
  position: fixed;
  width: 50px;
  height: 50px;
  top: 10px;
  right: 10px;
  border-radius: 25px;
  color: black;
  border-color: black;
  background-color: #eb459e;
  overflow: hidden;
`;

const CircleLink = styled.a`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  text-decoration: none;
  font-size: 30px;
`;

interface UserButtonProps extends ConnectUserButton {
  userActions: UserActions;
  children: React.ReactNode;
  redirect: boolean;
  show: boolean;
}
type UserButtonState = {
  displayName: Readonly<DisplayName> | undefined;
  ready: boolean;
};

class UserButton extends PureComponent<UserButtonProps, UserButtonState> {
  constructor(props: Readonly<UserButtonProps>) {
    super(props);
    this.state = { displayName: undefined, ready: false };
  }

  componentDidUpdate(
    prevProps: Readonly<UserButtonProps>,
    _prevState: Readonly<UserButtonState>,
  ): void {
    const { user: prevUser } = prevProps;
    const { user, userActions, dispatch } = this.props;
    const { ready } = this.state;
    if (!ready) {
      this.setState(
        {
          ready: true,
        },
        () => {
          userActions.currentUser((user) => {
            const { redirect } = this.props;
            if (!user.logged && redirect) {
              redirectLogin();
            }
            dispatch(setUser({ user: user.logged ? user : undefined }));
          });
        },
      );
    }
    if (user?.displayName !== prevUser?.displayName) {
      this.setState({
        displayName: user?.displayName,
      });
    }
  }

  render() {
    const { children, user, show } = this.props;
    const { displayName } = this.state;
    let initial = '';
    if (displayName?.length) {
      initial = displayName[0].toUpperCase();
    }
    return (
      <React.Fragment>
        {user && show ? (
          <Circle>
            <CircleLink href="/profile">{initial}</CircleLink>
          </Circle>
        ) : null}
        {children}
      </React.Fragment>
    );
  }
} // UserButton

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(UserButton);

type ConnectUserButton = ConnectedProps<typeof connector>;
