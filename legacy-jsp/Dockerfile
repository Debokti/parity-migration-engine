# SCF legacy monolith (Java 17, embedded Tomcat 9 via ServerMain).
# Production knobs are environment-driven; nothing secret is baked in:
#   PARITY_ENV=production  disables the /__parity/* dev endpoints
#   PARITY_BRIDGE_SECRET   HMAC secret for auth-bridge tokens (required in prod)
#   JAVA_OPTS              e.g. -Dserver.port=8080 -Dscf.db.url=jdbc:h2:file:/data/scf-db
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B -DskipTests package

FROM eclipse-temurin:17-jre AS runtime
WORKDIR /app
COPY --from=build /src/target/classes ./classes
COPY --from=build /src/target/lib ./lib
COPY --from=build /src/src/main/webapp ./src/main/webapp
VOLUME /data
ENV PARITY_ENV=production \
    JAVA_OPTS="-Dserver.port=8080 -Dscf.db.url=jdbc:h2:file:/data/scf-db;DB_CLOSE_DELAY=-1"
EXPOSE 8080
# ServerMain resolves src/main/webapp relative to the working directory.
CMD ["sh", "-c", "java $JAVA_OPTS -cp 'classes:lib/*' com.scf.config.ServerMain"]
