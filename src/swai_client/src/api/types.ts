export type MHash = string & { _mHash: void };
export type Token = string & { _token: void };

export type UserId = string & { _userId: void };
export type Username = string & { _username: void };

type UserPermissions = {
  canCreateTopic: Readonly<boolean>;
};
export type User = {
  token: Readonly<Token>;
  name: Readonly<Username>;
  userId: Readonly<UserId>;
  permissions: Readonly<UserPermissions>;
};

type ApiUserPermissions = {
  can_create_topic: Readonly<boolean>;
};
export type ApiLoginResponse = {
  token: Readonly<Token>;
  user: Readonly<Username>;
  userid: Readonly<UserId>;
  permissions: Readonly<ApiUserPermissions>;
};
export type ApiLogout = {
  success: boolean;
};

export function toUser(userResp: Readonly<ApiLoginResponse>): Readonly<User> {
  const { user, userid, permissions, ...rest } = userResp;
  return {
    name: user,
    userId: userid,
    permissions: {
      canCreateTopic: permissions.can_create_topic,
    },
    ...rest,
  };
}

export type ApiTopic = {
  topics: Readonly<{ [key: string]: string }>;
  next: Readonly<number>;
};

export type ApiRead = {
  messages: Readonly<{ [key: string]: string }>;
  skipped: Readonly<MHash[]>;
};

export type ApiLinkResponse = {
  parent: Readonly<MHash>;
  child: Readonly<MHash>;
  user: Readonly<Username> | undefined;
  userid: Readonly<UserId> | undefined;
  first: Readonly<number>;
  votes: ApiVotes;
  meta: Readonly<string>;
};

type ApiVote = {
  count: Readonly<number>;
  uservoted: Readonly<boolean>;
};
type Vote = {
  count: Readonly<number>;
  userVoted: Readonly<boolean>;
};
export type VoteType = 'honor' | 'up' | 'down';
export type VoteTypeExt = VoteType | 'view' | 'ack' | 'skip';
export type RichVote = {
  voteType: VoteType;
  count: number;
  userVoted: boolean;
};
export const VOTE_TYPES: VoteType[] = ['honor', 'up', 'down'];
export type ApiVotes = Readonly<{ [key in VoteType]?: Readonly<ApiVote> }>;
type Votes = Readonly<{ [key in VoteType]?: Readonly<Vote> }>;

export type ValidLink = {
  invalid?: Readonly<false>;
  parent: Readonly<MHash>;
  child: Readonly<MHash>;
  username: Readonly<Username> | undefined;
  userId: Readonly<UserId> | undefined;
  first: Readonly<number>;
  votes: Votes;
  meta: Readonly<string>;
};
type InvalidLink = {
  invalid: Readonly<true>;
};
export type Link = ValidLink | InvalidLink;
export const INVALID_LINK: Readonly<InvalidLink> = { invalid: true };

export function toLink(link: Readonly<ApiLinkResponse>): Readonly<ValidLink> {
  const { user, userid, votes, ...rest } = link;

  function convertVote(vote: ApiVote | undefined): Vote | undefined {
    if (vote === undefined) {
      return undefined;
    }
    const { count, uservoted } = vote;
    return {
      count,
      userVoted: uservoted,
    };
  }

  return {
    username: user,
    userId: userid,
    votes: {
      up: convertVote(votes.up),
      down: convertVote(votes.down),
      honor: convertVote(votes.honor),
    },
    ...rest,
  };
}

export type ApiLinkList = {
  links: Readonly<Readonly<ApiLinkResponse>[]>;
  next: Readonly<number>;
};

export function toLinks(
  links: Readonly<Readonly<ApiLinkResponse>[]>,
): Readonly<Readonly<ValidLink>[]> {
  return links.map((link) => toLink(link));
}
