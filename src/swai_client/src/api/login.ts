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
import { URL_PREFIX } from '../misc/constants';
import {
  ApiLoginResponse,
  ApiPasswordResetTokenResponse,
  Password,
  PasswordResetTokenResponse,
  ResetToken,
  User,
  UserName,
  toUser,
} from './types';

export type LoginApiProvider = {
  getUser: () => Promise<Readonly<User> | null>;
  loginUser: (
    name: Readonly<UserName>,
    password: Readonly<Password>,
  ) => Promise<Readonly<User> | null>;
  getResetPasswordToken: (
    name: Readonly<UserName>,
  ) => Promise<Readonly<PasswordResetTokenResponse>>;
  resetPassword: (
    resetToken: Readonly<ResetToken>,
    password: Readonly<Password>,
  ) => Promise<Readonly<User> | null>;
  logout: () => Promise<Readonly<User> | null>;
};

export const DEFAULT_LOGIN_API: LoginApiProvider = {
  getUser: async () => {
    const res = await fetch(`${URL_PREFIX}/login`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });
    if (!res.ok) {
      throw new Error(
        `Error in request ${res} (${res.status}): ${res.statusText}`,
      );
    }
    const obj = (await res.json()) as ApiLoginResponse;
    return toUser(obj);
  },
  loginUser: async (name, password) => {
    const res = await fetch(`${URL_PREFIX}/login`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        password,
      }),
    });
    if (!res.ok) {
      throw new Error(
        `Error in request ${res} (${res.status}): ${res.statusText}`,
      );
    }
    const obj = (await res.json()) as ApiLoginResponse;
    return toUser(obj);
  },
  getResetPasswordToken: async (name) => {
    const res = await fetch(`${URL_PREFIX}/reset_password_token`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
      }),
    });
    if (!res.ok) {
      throw new Error(
        `Error in request ${res} (${res.status}): ${res.statusText}`,
      );
    }
    const { user_name, reset_token } =
      (await res.json()) as ApiPasswordResetTokenResponse;
    return {
      name: user_name,
      resetToken: reset_token,
    };
  },
  resetPassword: async (resetToken, password) => {
    const res = await fetch(`${URL_PREFIX}/reset_password`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        reset_token: resetToken,
        password,
      }),
    });
    if (!res.ok) {
      throw new Error(
        `Error in request ${res} (${res.status}): ${res.statusText}`,
      );
    }
    const obj = (await res.json()) as ApiLoginResponse;
    return toUser(obj);
  },
  logout: async () => {
    const res = await fetch(`${URL_PREFIX}/logout`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      throw new Error(
        `Error in request ${res} (${res.status}): ${res.statusText}`,
      );
    }
    const obj = (await res.json()) as ApiLoginResponse;
    return toUser(obj);
  },
};
