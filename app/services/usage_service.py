from app.repositories.usage_repository import UsageRepository


class UsageService:

    def __init__(self, db):
        self.repository = UsageRepository(db)

    def record_usage(self, usage):
        return self.repository.create(usage)

    def list_usage(self):
        return self.repository.get_all()