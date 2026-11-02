package com.scf.repository;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;

public final class Database {
    public static final String URL = System.getProperty("scf.db.url",
            "jdbc:h2:file:./data/scf-db;DB_CLOSE_DELAY=-1;AUTO_SERVER=TRUE");

    public static Connection connection() throws SQLException {
        return DriverManager.getConnection(URL, "sa", "");
    }

    public static void initialize() {
        try (Connection c = connection()) {
            run(c, "/schema.sql");
            if (isEmpty(c)) {
                run(c, "/seed.sql");
            }
        } catch (Exception e) {
            throw new IllegalStateException("Database initialization failed", e);
        }
    }

    public static void reset() {
        try (Connection c = connection()) {
            try (Statement s = c.createStatement()) {
                s.execute("DROP ALL OBJECTS");
            }
            run(c, "/schema.sql");
            run(c, "/seed.sql");
        } catch (Exception e) {
            throw new IllegalStateException("Database reset failed", e);
        }
    }

    private static boolean isEmpty(Connection c) throws SQLException {
        try (Statement s = c.createStatement(); ResultSet r = s.executeQuery("SELECT COUNT(*) FROM invoices")) {
            return !r.next() || r.getInt(1) == 0;
        }
    }

    private static void run(Connection c, String resource) throws Exception {
        try (InputStream in = Database.class.getResourceAsStream(resource)) {
            if (in == null) throw new FileNotFoundException(resource);
            String sql = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            for (String statement : sql.split(";")) {
                if (!statement.isBlank()) {
                    try (Statement s = c.createStatement()) {
                        s.execute(statement);
                    }
                }
            }
        }
    }
}
