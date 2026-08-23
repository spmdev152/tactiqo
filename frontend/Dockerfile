FROM oven/bun:1.3.14-debian

WORKDIR /app

ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1

RUN chown bun:bun /app

USER bun

COPY --chown=bun:bun package.json bun.lock ./

RUN bun install --frozen-lockfile

COPY --chown=bun:bun . .

EXPOSE 3000

CMD ["bun", "run", "dev"]
