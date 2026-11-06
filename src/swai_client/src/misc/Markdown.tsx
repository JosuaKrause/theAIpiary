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
  &:hover,
  &:focus {
    color: var(--md-anchor-hover);
  }
`;

const Paragraph = styled.p`
  padding: 0;
`;

const MD_COMPONENTS: Partial<
  Omit<NormalComponents, keyof SpecialComponents> & SpecialComponents
> = {
  a: ({ node: _, ...props }) => <Link {...props} />,
  p: ({ node: _, ...props }) => <Paragraph {...props} />,
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
  backLink?: string;
  children?: React.ReactNode;
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
      { appName: '', url: null, children: null },
      { content: null, inFlight: false },
    );
  }

  componentDidUpdate(
    prevProps: Readonly<StaticMarkdownProps>,
    _prevState: Readonly<StaticMarkdownState>,
  ) {
    const { url: prevUrl } = prevProps;
    const { url, appName, backLink } = this.props;
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
          const c1 = content.replaceAll('<appName>', appName);
          const c2 = backLink ? c1.replaceAll('<backLink>', backLink) : c1;
          this.setState({
            content: c2,
            inFlight: false,
          });
        },
      );
    }
  }

  render() {
    const { children } = this.props;
    const { content } = this.state;
    if (!content) {
      return children;
    }
    return <Markdown>{content}</Markdown>;
  }
} // StaticMarkdown
