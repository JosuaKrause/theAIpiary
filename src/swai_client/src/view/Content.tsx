import { PureComponent, ReactElement } from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';
import { NormalComponents } from 'react-markdown/lib/complex-types';
import { SpecialComponents } from 'react-markdown/lib/ast-to-react';

const ContentBox = styled.div`
  margin: auto 0;
  width: var(--md-size-w);
  height: var(--md-size-h);
  overflow-y: auto;
  overflow-x: hidden;
  word-break: break-word;
`;

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

type ContentProps = { children: string };

export default class Content extends PureComponent<ContentProps> {
  render(): ReactElement {
    const { children } = this.props;
    return (
      <ContentBox>
        <ReactMarkdown
          skipHtml={true}
          components={MD_COMPONENTS}>
          {children}
        </ReactMarkdown>
      </ContentBox>
    );
  }
} // Content
