package internal

import "github.com/go-playground/validator/v10"

type ValidatorInterface interface {
	ValidateCostPayload(p *CostPayload) error
	ValidateForecastPayload(p *ForecastPayload) error
}

type Validator struct {
	validate *validator.Validate
}

// instantiate validator
func NewValidator() *Validator {
	return &Validator{
		validate: validator.New(),
	}
}

// validate against struct
func (v *Validator) ValidateCostPayload(p *CostPayload) error {
	return v.validate.Struct(p)
}

// validate against struct
func (v *Validator) ValidateForecastPayload(p *ForecastPayload) error {
	return v.validate.Struct(p)
}
