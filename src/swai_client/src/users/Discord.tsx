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
