import { DEFAULT_LOGIN_API, LoginApiProvider } from '../api/login';
import {
  Password,
  ResetToken,
  User,
  UserName,
  WorkerToken,
} from '../api/types';

type UserCallback = (user: Readonly<User> | null) => void;

export default class UserActions {
  private readonly api: LoginApiProvider;

  constructor(api?: LoginApiProvider) {
    this.api = api ?? DEFAULT_LOGIN_API;
  }

  async currentUser(updateUser: UserCallback) {
    const user = await this.api.getUser();
    updateUser(user);
  }

  async login(
    username: Readonly<UserName>,
    password: Readonly<Password>,
    updateUser: UserCallback,
  ) {
    const user = await this.api.loginUser(username, password);
    updateUser(user);
  }

  async changePassword(
    resetToken: Readonly<ResetToken>,
    password: Readonly<Password>,
    updateUser: UserCallback,
  ) {
    const user = await this.api.resetPassword(resetToken, password);
    updateUser(user);
  }

  async logout(updateUser: UserCallback) {
    const user = await this.api.logout();
    updateUser(user);
  }

  async getWorkerToken(
    updateToken: (workerToken: Readonly<WorkerToken>) => void,
  ) {
    const workerToken = await this.api.getWorkerToken();
    updateToken(workerToken);
  }
} // UserActions
