.PHONY: build install tidy vet clean snapshot

build: tidy
	go build -o docmanfu .

install: tidy
	go install .

tidy:
	go mod tidy

vet:
	go vet ./...

# Build release archives locally without publishing (requires goreleaser)
snapshot:
	goreleaser release --snapshot --clean

clean:
	rm -f docmanfu
	rm -rf dist/
