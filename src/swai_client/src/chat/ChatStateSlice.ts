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
import { SessionId } from '../api/types';

type ChatState = {
  currentSession: Readonly<SessionId> | undefined;
};

type SetAction = {
  payload: {
    session: Readonly<SessionId> | undefined;
  };
};

type ChatReducers = {
  setSession: (state: ChatState, action: SetAction) => void;
};

const chatStateSlice = createSlice<ChatState, ChatReducers, string>({
  name: 'chatState',
  initialState: {
    currentSession: undefined,
  },
  reducers: {
    setSession: (state, action) => {
      const { session } = action.payload;
      state.currentSession = session;
    },
  },
});

export const { setSession } = chatStateSlice.actions;

export default chatStateSlice.reducer;
