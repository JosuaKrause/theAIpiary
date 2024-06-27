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
  align-self: center;
  display: flex;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 15px;
  background-color: #5865f2;
  color: white;
  text-decoration: none;

  &:visited {
    background-color: #5865f2;
    color: white;
  }

  &:hover,
  &:active,
  &:focus {
    background-color: #5865f2;
    color: white;
    opacity: 0.9;
  }
`;

const Img = styled.img`
  align-self: center;
  width: auto;
  height: auto;
  max-width: 20px;
  max-height: 20px;
`;

type DiscordProps = ConnectDiscord;
type DiscordState = Record<string, void>;

class Discord extends PureComponent<DiscordProps, DiscordState> {
  constructor(props: Readonly<DiscordProps>) {
    super(props);
    this.state = {};
  }

  render() {
    const { user } = this.props;
    if (!user) {
      return null;
    }
    const { discord } = user;
    if (!discord) {
      return null;
    }
    return (
      <Link href={discord}>
        <Img
          src="/discord-mark-white.png"
          alt="Discord"
          title="Join the Discord Server!"
        />
      </Link>
    );
  }
} // Discord

const connector = connect((state: RootState) => ({
  user: state.userState.currentUser,
}));

export default connector(Discord);

type ConnectDiscord = ConnectedProps<typeof connector>;
