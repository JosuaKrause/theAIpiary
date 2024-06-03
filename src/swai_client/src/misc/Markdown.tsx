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
import ReactMarkdown from 'react-markdown';
import { SpecialComponents } from 'react-markdown/lib/ast-to-react';
import { NormalComponents } from 'react-markdown/lib/complex-types';
import styled from 'styled-components';

const Link = styled.a`
  color: var(--md-anchor);

  &:visited {
    color: var(--md-anchor);
  }
  &:active {
    color: var(--md-anchor);
  }
  &:hover {
    color: var(--md-anchor-hover);
  }
`;

const MD_COMPONENTS: Partial<
  Omit<NormalComponents, keyof SpecialComponents> & SpecialComponents
> = {
  a: ({ node: _, ...props }) => <Link {...props} />,
};

type MarkdownProps = {
  children: string;
};

export class Markdown extends PureComponent<MarkdownProps> {
  render() {
    const { children } = this.props;
    return (
      <ReactMarkdown
        skipHtml={true}
        components={MD_COMPONENTS}>
        {children}
      </ReactMarkdown>
    );
  }
} // Markdown

type StaticMarkdownProps = {
  url: string | null;
  appName: string;
};
type StaticMarkdownState = {
  content: string | null;
  inFlight: boolean;
};

export class StaticMarkdown extends PureComponent<
  StaticMarkdownProps,
  StaticMarkdownState
> {
  constructor(props: Readonly<StaticMarkdownProps>) {
    super(props);
    this.state = {
      content: null,
      inFlight: false,
    };
  }

  componentDidMount() {
    this.componentDidUpdate(
      { appName: '', url: null },
      { content: null, inFlight: false },
    );
  }

  componentDidUpdate(
    prevProps: Readonly<StaticMarkdownProps>,
    _prevState: Readonly<StaticMarkdownState>,
  ) {
    const { url: prevUrl } = prevProps;
    const { url, appName } = this.props;
    const { content, inFlight } = this.state;
    if (content && prevUrl !== url) {
      this.setState({ inFlight: false, content: null });
    }
    if (url && !content && !inFlight) {
      this.setState(
        {
          inFlight: true,
        },
        async () => {
          const { url: contentUrl } = this.props;
          const resp = await fetch(`${url}`, { method: 'GET' });
          const content = await resp.text();
          if (url !== contentUrl) {
            return;
          }
          this.setState({
            content: content.replaceAll('<appName>', appName),
            inFlight: false,
          });
        },
      );
    }
  }

  render() {
    const { content } = this.state;
    if (!content) {
      return null;
    }
    return <Markdown>{content}</Markdown>;
  }
} // StaticMarkdown
