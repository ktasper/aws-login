# aws-login
A python util to assist with logging into AWS via aws-adfs tool.



# Usage
## Install
- Install via `pip`
```shell
pip install aws-adfs-login-helper
```

## Config
- All config will be in `$HOME/.config/aws-login.yaml`
```yaml
profiles:
  eu:
    region: eu-west-1
    username: "aws\\me"
    adfs-host: adfs.hostname
  us:
    region: us-east-1
    username: "aws\\me"
    adfs-host: "adfs.com"

environments:
  dev:
    state_account_id: "12312312312"
    target_account_id: "12512512512"
    session_duration: 900
  tf-stage:
    state_account_id: "5215125125125"
    target_account_id: "621612612612"
    session_duration: 900
  prod:
    state_account_id: "4124152186221"

defaults:
  role_name: "ROLE-Root"
  session_duration: 900

ssl:
  ca_bundle_path: "~/.ssh/aws_certs/eu.pem"
  verify_ssl: true
```
- `state_account_id` = Where the terraform state is located, if this is the only value set will default `target_account_id` to be the same. 
- `target_account_id` = The target for our terraform. If you have state in a shared account you want to use shared as the `state` account and the target as well.. the target.


## Login

- Since most times you will need to enter your ADFS password for the first time of the day, you should call the tool like this for the initial invocation for the day.
  - As a result you need to login without exporting the variables
```shell
aws-login -e dev
```
- This will call aws-adfs and ask for your password / 2FA etc.

- For actual usage you want to call it as so:
```shell
eval $(aws-login login -e prod)
```
- As we have already authed to adfs we can just run this and trust our variables get exported.

## Extras
- `aws-login --help` for extra help info
- `aws-login login --help ` Extra help for the `login` command.
- `aws-login --install-completion` Shell completion
- `aws-login list-environments` Prints all the envs you have.
- `aws-login list-profiles` prints all the profiles you have, so you don't have to `cat` the config file.


# Dev Notes
python -m build 
twine upload -r pypi dist/*