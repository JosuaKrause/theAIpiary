import { configureStore } from '@reduxjs/toolkit';
import chatStateSliceReducer from './chat/ChatStateSlice';
import userStateSliceReducer from './users/UserStateSlice';

const store = configureStore({
  reducer: {
    userState: userStateSliceReducer,
    chatState: chatStateSliceReducer,
  },
});

export default store;

export type RootState = ReturnType<typeof store.getState>;
// FIXME for reference
// ts-unused-exports:disable-next-line
export type AppDispatch = typeof store.dispatch;
