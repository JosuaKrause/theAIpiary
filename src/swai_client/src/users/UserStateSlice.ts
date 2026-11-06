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
import { createSlice } from '@reduxjs/toolkit';
import { User } from '../api/types';

type UserState = {
  currentUser: Readonly<User> | undefined;
};

type SetAction = {
  payload: {
    user: Readonly<User> | undefined;
  };
};

type UserReducers = {
  setUser: (state: UserState, action: SetAction) => void;
};

const userStateSlice = createSlice<UserState, UserReducers, string>({
  name: 'userState',
  initialState: {
    currentUser: undefined,
  },
  reducers: {
    setUser: (state, action) => {
      const { user } = action.payload;
      state.currentUser = user;
    },
  },
});

export const { setUser } = userStateSlice.actions;

export default userStateSlice.reducer;
