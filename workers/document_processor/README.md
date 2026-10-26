# Document processor

Reserved for a dedicated Django-managed worker entrypoint backed by the database job queue. It may reuse business logic from `apps/api`, but its process lifecycle stays separate. No job lifecycle is implemented by IC-001.

