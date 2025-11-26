package main

import (
	"fmt"
	"net/http"
)

type APIServer struct{}

// cosntructor
func NewAPIServer() *APIServer {
	return &APIServer{}
}

// start http server
func (s *APIServer) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /metrics/cost", s.handleCostEngine)
	mux.HandleFunc("POST /metrics/forecast", s.handleForecast)

	return http.ListenAndServe(":8080", mux)
}

// handler function for POST /metrics/cost request
func (s *APIServer) handleCostEngine(w http.ResponseWriter, r *http.Request) {
	fmt.Println("Received post request for /metrics/cost")

}

// handler function for POST /metrics/forecast
func (s *APIServer) handleForecast(w http.ResponseWriter, r *http.Request) {
	fmt.Println("Received post request for /metrics/forecast")

}
