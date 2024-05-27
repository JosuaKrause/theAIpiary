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
import { MouseEventHandler, PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { WorkerToken } from '../api/types';
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

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
  }
`;

const Row = styled.div``;

interface ProfileProps extends ConnectProfile {
  userActions: UserActions;
}
type ProfileState = {
  workerToken: Readonly<WorkerToken> | null;
};

class Profile extends PureComponent<ProfileProps, ProfileState> {
  constructor(props: Readonly<ProfileProps>) {
    super(props);
    this.state = { workerToken: null };
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
      if (!user.name) {
        redirectWelcome();
      }
    });
  };

  render() {
    const { user } = this.props;
    const { workerToken } = this.state;
    return (
      <VMain>
        {user ? <Row>User: {user?.name}</Row> : null}
        <Row>
          <input
            name="workertoken"
            type="button"
            value="Get Worker Token"
            onClick={this.handleWorkerTokenClick}
          />
          {workerToken ? (
            <div>
              Worker Token: <pre>{workerToken}</pre>
            </div>
          ) : null}
        </Row>
        <Row>
          <input
            name="logout"
            type="button"
            value="Logout"
            onClick={this.handleLogoutClick}
          />
        </Row>
      </VMain>
    );
  }
} // Profile

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Profile);

type ConnectProfile = ConnectedProps<typeof connector>;
