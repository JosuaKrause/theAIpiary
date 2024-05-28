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
import React, { MouseEventHandler, PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { DisplayName, UserEmail, WorkerToken } from '../api/types';
import { redirectWelcome } from '../misc/common';
import { RootState } from '../store';
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
  }
`;

const Group = styled.div`
  margin: 5px;
  padding: 5px;
  border: 1px solid darkgray;
  width: 100%;
`;

const Row = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: space-between;
`;

interface ProfileProps extends ConnectProfile {
  userActions: UserActions;
}
type ProfileState = {
  createdUser: Readonly<UserEmail> | undefined;
  workerToken: Readonly<WorkerToken> | null;
};

class Profile extends PureComponent<ProfileProps, ProfileState> {
  private readonly createNameRef: React.RefObject<HTMLInputElement>;
  private readonly createEmailRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<ProfileProps>) {
    super(props);
    this.state = { createdUser: undefined, workerToken: null };
    this.createNameRef = React.createRef();
    this.createEmailRef = React.createRef();
  }

  handleWorkerTokenClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    userActions.getWorkerToken((workerToken) => {
      this.setState({ workerToken });
    });
  };

  handleLogoutClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    userActions.logout((user) => {
      if (!user.logged) {
        redirectWelcome();
      }
    });
  };

  handleCreateUserClick: MouseEventHandler<HTMLInputElement> = (e) => {
    e.preventDefault();
    const { userActions } = this.props;
    const emailInput = this.createEmailRef.current;
    const nameInput = this.createNameRef.current;
    if (!emailInput || !nameInput) {
      return;
    }
    const email = emailInput.value as UserEmail;
    const displayName = nameInput.value as DisplayName;
    if (!email || !displayName) {
      return;
    }
    userActions.createUser(email, displayName, (newEmail) => {
      emailInput.value = '';
      nameInput.value = '';
      this.setState({ createdUser: newEmail });
    });
  };

  render() {
    const { user } = this.props;
    const { workerToken, createdUser } = this.state;
    return (
      <VMain>
        <Group>
          {user ? <Row>User: {user.displayName}</Row> : null}
          {user ? <Row>Email: {user.email}</Row> : null}
        </Group>
        {user && user.capabilities.createUser ? (
          <Group>
            <Row>Create User:</Row>
            <Row>
              <label htmlFor="createemail">New User Email:</label>
              <input
                autoComplete="off"
                name="createemail"
                type="text"
                ref={this.createEmailRef}
              />
            </Row>
            <Row>
              <label htmlFor="createdisplay">New User Display Name:</label>
              <input
                autoComplete="off"
                name="createdisplay"
                type="text"
                ref={this.createNameRef}
              />
            </Row>
            <Row>
              <input
                name="createuser"
                type="button"
                value="Create User"
                onClick={this.handleCreateUserClick}
              />
            </Row>
            {createdUser ? <Row>Sent email to: {createdUser}</Row> : null}
          </Group>
        ) : null}
        {user && user.capabilities.registerOwnWorker ? (
          <Group>
            <Row>Add a Worker Bee</Row>
            <Row>
              <input
                name="workertoken"
                type="button"
                value="Get Worker Token"
                onClick={this.handleWorkerTokenClick}
              />
            </Row>
            {workerToken ? (
              <Row>
                Worker Token: <pre>{workerToken}</pre>
              </Row>
            ) : null}
          </Group>
        ) : null}
        <Group>
          <Row>
            <input
              name="logout"
              type="button"
              value="Logout"
              onClick={this.handleLogoutClick}
            />
          </Row>
        </Group>
      </VMain>
    );
  }
} // Profile

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Profile);

type ConnectProfile = ConnectedProps<typeof connector>;
