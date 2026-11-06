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
import styled from 'styled-components';

const Span = styled.span`
  cursor: pointer;
`;

type AutoHideProps = {
  title: string;
  children: React.ReactNode;
};
type AutoHideState = {
  hide: boolean;
};

export default class AutoHide extends PureComponent<
  AutoHideProps,
  AutoHideState
> {
  constructor(props: Readonly<AutoHideProps>) {
    super(props);
    this.state = {
      hide: true,
    };
  }

  onClick: React.MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.isDefaultPrevented()) {
      return;
    }
    e.preventDefault();
    this.setState({ hide: false });
  };

  render() {
    const { children, title } = this.props;
    const { hide } = this.state;
    if (hide) {
      return <Span onClick={this.onClick}>{title}</Span>;
    }
    return children;
  }
} // AutoHide
