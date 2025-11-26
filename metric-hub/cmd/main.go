package main

import (
	"log"
)

func main() {
	server := NewAPIServer()
	log.Println("Starting server on port 8080")

	if err := server.Start(); err != nil {
		log.Fatal(err)
	}
}
