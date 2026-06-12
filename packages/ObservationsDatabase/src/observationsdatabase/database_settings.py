from configparser import SafeConfigParser


class DatabaseConfiguration:
    def __init__(self, db_type, **kwargs):

        self.db_type = None
        self.username = None
        self.password = None
        self.host = None
        self.port = None
        self.database_name =None
        self.connectionstring = None

        if 'ini_file' not in kwargs:
            self.db_type = db_type.lower()
            if self.db_type == "postgres":
                if 'ini_file' not in kwargs:
                    self.username = kwargs.get("username")
                    self.password = kwargs.get("password")
                    self.host = kwargs.get("host", "localhost")
                    self.port = kwargs.get("port", 5432)
                    self.database_name = kwargs.get("database_name")
                    self.connectionstring = kwargs.get("connectionstring", None)
            elif self.db_type == "sqlite":
                if 'ini_file' not in kwargs:
                    self.file_path = kwargs.get("file_path")
            else:
                raise ValueError("Unsupported database type. Use 'postgres' or 'sqlite'.")

        else:
            config_file = SafeConfigParser()
            config_file.read(kwargs['ini_file'])
            self.db_type = config_file.get('Database', 'db_type')
            if self.db_type == "postgres":
                self.username = config_file.get("Database", "user")
                self.password = config_file.get("Database","password")
                self.host = config_file.get("Database","host")
                self.port = config_file.get("Database","port")
                self.database_name = config_file.get("Database", "name")
                self.connectionstring = config_file.get("Database", "connectionstring")

            elif self.db_type == "sqlite":
                self.file_path = config_file.get("Database", "file_path")

            else:
                raise ValueError("Unsupported database type. Use 'postgres' or 'sqlite'.")

    def get_connection_string(self):
        if self.db_type == "postgres":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == "sqlite":
            return f"sqlite:///{self.file_path}"

