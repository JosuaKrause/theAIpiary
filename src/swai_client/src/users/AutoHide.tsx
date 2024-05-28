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
