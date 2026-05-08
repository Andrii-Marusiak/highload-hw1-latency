FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -mod=mod -o observability-service .

FROM alpine:3.21

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder /app/observability-service .

USER appuser

EXPOSE 8080
EXPOSE 9090

ENTRYPOINT ["./observability-service"]
