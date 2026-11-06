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
import { DEFAULT_LOGIN_API, LoginApiProvider } from '../api/login';
import {
  ApiUserCapability,
  DisplayName,
  LoginInfo,
  Password,
  ResetToken,
  SessionInfo,
  User,
  UserEmail,
  UserInfo,
  WorkerInfo,
  WorkerToken,
} from '../api/types';

type UserCallback = (user: Readonly<User> | Readonly<LoginInfo>) => void;
type EmailOpCallback = (email: Readonly<UserEmail> | undefined) => void;
type UserListCallback = (users: UserInfo[]) => void;
type ChatListCallback = (chats: SessionInfo[]) => void;
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

  async changeCapability(
    email: Readonly<UserEmail>,
    capability: ApiUserCapability,
    setActive: boolean,
    onDone: () => void,
  ) {
    await this.api.changeCapability(email, capability, setActive);
    onDone();
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
