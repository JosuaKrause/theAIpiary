import { configureStore } from '@reduxjs/toolkit';
import modalStateSliceReducer from './modal/ModalStateSlice';
// import viewStateSliceReducer from './view/ViewStateSlice';
// import userStateSliceReducer from './users/UserStateSlice';
import chatStateSliceReducer from './chat/ChatStateSlice';

const store = configureStore({
  reducer: {
    // viewState: viewStateSliceReducer,
    // userState: userStateSliceReducer,
    modalState: modalStateSliceReducer,
    chatState: chatStateSliceReducer,
  },
});

export default store;

export type RootState = ReturnType<typeof store.getState>;
// FIXME for reference
// ts-unused-exports:disable-next-line
export type AppDispatch = typeof store.dispatch;
