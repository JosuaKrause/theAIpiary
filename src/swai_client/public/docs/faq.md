### Frequently Asked Questions

[Back](<backLink>)

- **What is this?**

  The **<appName>** is a swarm based ML compute engine that operates as
  inverse cloud. That is, the only cloud-based compute is used to render
  the website and coordinate ML tasks. The actual computation of ML tasks
  happens on client machines, called worker bees, that are provided by
  users and can be integrated in the swarm.

  The idea behind this is that, although people have powerful GPUs on their
  personal computer, the compute that those GPUs provide is rarely fully
  utilized. In those downtimes, this spare compute can be made available by
  offering it to the inverse cloud swarm. You can find information about how
  to integrate a machine into the swarm on your profile page.

- **Why would I make my GPU available?**

  Although, at this time, there is no compensation for making compute available
  to the swarm there are several advantages over just using the GPU locally.

  1) Integrating compute into the swarm keeps the swarm healthy for the benefit
    of every user. It also enables you to use your home compute on the go
    (e.g., on mobile) without having to create a complicated setup.

  2) When computing tasks you are not limited by your own compute. Every user
    has access to all compute in the swarm. This means, when, e.g., computing
    three tasks, they can be executed in parallel. With only a local setup they
    would have to be executed sequentially.

  3) Through model sharding, ML tasks requiring larger models than feasible on
    your own hardware can be easily distributed across the swarm. This enables
    the use of larger models than what would be possible with only a local GPU
    setup.

  4) When hooked into the swarm, workers typically don't get into the way of
    normal operations. Only if spare compute is available locally will it be
    made available to the swarm.

- **Security & Privacy**

  As the community is invite only at this time, a large component of security
  and privacy considerations are based on mutual trust. That said, there is no
  connection between users and their ML tasks. Worker bees do *not* know which
  user has initiated the task they are currently computing. Keep in mind,
  however, that the tasks themselves have to be made available to the worker
  and, as such, workers are at least partially aware of what the data they
  are processing is about. If Personal Identifyable Information is part of this
  there is a possibility that a connection to a user could be established. We
  are taking security and privacy very seriously and are continuously working
  on making the system more secure and private for everyone.

- **Model Licenses**

  By using models through the **<appName>** you are implicitly agreeing to
  their respective licenses and terms. The **<appName>** is *not* responsible
  *nor* liable for any license breaches or violations.

- **Discord**

  If you have further comments, suggestions, or questions head to Discord. The
  link to the Discord server can be found on your profile page.

[Back](<backLink>)
