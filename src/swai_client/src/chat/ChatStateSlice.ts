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
