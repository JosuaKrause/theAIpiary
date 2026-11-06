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
import styled from 'styled-components';

const Link = styled.a`
  align-self: center;
  display: flex;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 15px;
  background-color: white;
  color: black;
  text-decoration: none;

  &:visited {
    background-color: c;
    color: black;
  }

  &:hover,
  &:active,
  &:focus {
    background-color: white;
    color: black;
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

type LogoProps = { appName: string };
type LogoState = Record<string, void>;

export default class Logo extends PureComponent<LogoProps, LogoState> {
  constructor(props: Readonly<LogoProps>) {
    super(props);
    this.state = {};
  }

  render() {
    const { appName } = this.props;
    return (
      <Link href="/">
        <Img
          src="/logo_inv_sq.png"
          alt={appName}
        />
      </Link>
    );
  }
} // Logo
