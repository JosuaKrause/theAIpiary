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
