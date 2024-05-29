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

const Img = styled.img`
  width: 30vw;
  height: 30vw;
`;

const Paragraph = styled.p`
  text-align: justify;
  margin: 10px;
  padding: 5px;
  max-width: 42vw;

  @media (hover: none) and (max-width: 480px) {
    max-width: 100vw;
  }
`;

const LinkParagraph = styled.p`
  margin: 10px;
  padding: 5px;
`;

const Link = styled.a`
  padding: 5px;
  margin: 10px;
  border-radius: 3px;
  border: 1px solid silver;
  font-weight: bold;
  color: silver;
  text-decoration: none;

  &:visited {
    color: silver;
  }

  &:hover {
    color: lightgray;
    background-color: var(--button-background);
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
        <Paragraph>
          The <strong>{appName}</strong> is a unique swarm-based ML compute
          engine. Here, members can contribute their spare computational power
          to create a collective intelligence. It&apos;s like a beehive buzzing
          with activity, where every bee plays a part in the success of the
          whole. But even those with limited computational resources can tap
          into the hive&apos;s collective power, making advanced AI accessible
          to all. Dive in and experience the power of swarm intelligence!
        </Paragraph>
        <LinkParagraph>
          {user ? (
            <Link href="/profile">Profile</Link>
          ) : (
            <Link href="/login">Login</Link>
          )}
        </LinkParagraph>
        <Img src="/logo_inv_lg.png" />
        <Paragraph>
          2024 &copyright;{' '}
          <Link href="https://www.josuakrause.com/">Josua Krause</Link>
        </Paragraph>
      </div>
    );
  }
}

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Welcome);

type ConnectWelcome = ConnectedProps<typeof connector>;
