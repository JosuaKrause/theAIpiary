import { PureComponent } from 'react';

type WelcomeProps = Record<string, void>;
type WelcomeState = Record<string, void>;

export default class Welcome extends PureComponent<
  WelcomeProps,
  WelcomeState
> {
  render() {
    return <div>Welcome to the AIpiary!</div>;
  }
}
