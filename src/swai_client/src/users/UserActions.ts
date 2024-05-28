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
import { DEFAULT_LOGIN_API, LoginApiProvider } from '../api/login';
import {
  DisplayName,
  LoginInfo,
  Password,
  ResetToken,
  SessionId,
  User,
  UserEmail,
  UserInfo,
  WorkerInfo,
  WorkerToken,
} from '../api/types';

type UserCallback = (user: Readonly<User> | Readonly<LoginInfo>) => void;
type EmailOpCallback = (email: Readonly<UserEmail> | undefined) => void;
type UserListCallback = (users: UserInfo[]) => void;
type ChatListCallback = (chats: SessionId[]) => void;
type WorkerListCallback = (workers: WorkerInfo[]) => void;

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
    username: Readonly<UserEmail>,
    password: Readonly<Password>,
    updateUser: UserCallback,
  ) {
    const user = await this.api.loginUser(username, password);
    updateUser(user);
  }

  async createUser(
    newEmail: Readonly<UserEmail>,
    displayName: Readonly<DisplayName>,
    onFinish: EmailOpCallback,
  ) {
    const email = await this.api.newUser(newEmail, displayName);
    onFinish(email);
  }

  async resetPassword(email: Readonly<UserEmail>, onFinish: EmailOpCallback) {
    const responseEmail = await this.api.getResetPasswordToken(email);
    onFinish(responseEmail);
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

  async getUsers(updateUsers: UserListCallback) {
    const users = await this.api.listUsers();
    updateUsers(users);
  }

  async getChats(updateChats: ChatListCallback) {
    const chats = await this.api.listChats();
    updateChats(chats);
  }

  async getWorkers(updateWorkers: WorkerListCallback) {
    const workers = await this.api.listWorkers();
    updateWorkers(workers);
  }
} // UserActions
