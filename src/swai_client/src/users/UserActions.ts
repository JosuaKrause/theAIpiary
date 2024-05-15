import { DEFAULT_PRIVILEGE_API, PrivilegeApiProvider } from '../api/privilege';
import {
  Link,
  MHash,
  Token,
  toLink,
  toUser,
  User,
  Username,
  ValidLink,
  VoteTypeExt,
} from '../api/types';

export default class UserActions {
  private readonly api: PrivilegeApiProvider;

  constructor(api?: PrivilegeApiProvider) {
    this.api = api ?? DEFAULT_PRIVILEGE_API;
  }

  async login(username: Readonly<Username>): Promise<User> {
    const res = await this.api.login(username);
    return toUser(res);
  }

  async logout(token: Readonly<Token>): Promise<boolean> {
    const res = await this.api.logout(token);
    return !!res.success;
  }

  async activeUser(
    token: Readonly<Token> | undefined,
  ): Promise<User | undefined> {
    if (token === undefined) {
      return undefined;
    }
    const res = await this.api.userInfo(token);
    return toUser(res);
  }

  async vote(
    token: Readonly<Token>,
    parent: Readonly<MHash>,
    child: Readonly<MHash>,
    votes: Readonly<VoteTypeExt[]>,
    isAdd: boolean,
  ): Promise<Link> {
    const res = await this.api.vote(token, parent, child, votes, isAdd);
    return toLink(res);
  }

  async writeMessage(
    token: Readonly<Token>,
    parent: Readonly<MHash>,
    text: string,
  ): Promise<ValidLink> {
    const res = await this.api.writeMessage(token, parent, text);
    return toLink(res);
  }
} // UserActions
