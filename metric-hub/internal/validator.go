package internal

import "github.com/go-playground/validator/v10"

type ValidatorInterface interface {
	Validate(v interface{}) error
}

type Validator struct {
	validate *validator.Validate
}

// instantiate validator
func NewValidator() ValidatorInterface {
	return &Validator{
		validate: validator.New(),
	}
}

func (v *Validator) Validate(payload interface{}) error {
	return v.validate.Struct(payload)
}
