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
import { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { RootState } from '../store';

const Link = styled.a`
  color: silver;
  text-decoration: none;

  &:visited {
    color: silver;
  }
`;

interface WelcomeProps extends ConnectWelcome {
  appName: string;
}
type WelcomeState = Record<string, void>;

class Welcome extends PureComponent<WelcomeProps, WelcomeState> {
  render() {
    const { user, appName } = this.props;
    return (
      <div>
        <h3>Welcome to the {appName}!</h3>
        <p>
          The {appName} is a swarm based inference engine with all compute
          provided by their members.
        </p>
        <p>
          {user ? (
            <Link href="/profile">Profile</Link>
          ) : (
            <Link href="/login">Login</Link>
          )}
        </p>
      </div>
    );
  }
}

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Welcome);

type ConnectWelcome = ConnectedProps<typeof connector>;
