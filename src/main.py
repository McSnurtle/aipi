"""REST API infrastructure for querying, posting and getting updates from the conversations DB"""
# TODO: implement oath2; https://fastapi.tiangolo.com/tutorial/security/first-steps/#create-main-py
# imports
import hashlib
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Response, status, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

import utils.db as db
import utils.model as model

# variables
app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

db.init_tables()


# classes
class Context(BaseModel):
    cid: int
    owner: int
    task: str
    model_id: str
    context: dict
    updated_at: Any


class User(BaseModel):
    username: str
    uid: int
    created_at: Any


class UserInDB(User):
    password_hash: str


async def token_to_user(token: str) -> User:
    return UserInDB(**db.get_user_by_username(token))  # TODO: reverse lookup token NOT username


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    user = await token_to_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must sign in to perform this action",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


# routes
@app.get("/")
async def read_root() -> dict:
    return {"status": 200}


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict:
    """Accepts form data of username and password, granting an OAuth2 token upon proper and valid completion."""
    user_data: dict = db.get_user_by_username(form_data.username)
    if not user_data:
        print(f"User tried to login with username {form_data.username} but no such user exists.")
        raise HTTPException(status_code=400, detail="Invalid username or password.")
    user = UserInDB(**user_data)
    if not db.is_correct_pass(user.username, form_data.password):
        print(f"User tried to login with username {form_data.username} but used an incorrect password.")
        raise HTTPException(status_code=400, detail="Invalid username or password.")

    # return {"access_token": hashlib.sha256(uuid.uuid4().bytes).hexdigest(), "token_type": "bearer"}   # TODO: implement this!
    return {"access_token": form_data.username, "token_type": "bearer"}


@app.post("/query/{model_id}+{task}/{prompt}")
async def query_model(model_id: str, task: str, prompt: str, user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Sends a query of `prompt` to `model` and returns the model's `response`. No context history or record is ever stored, this is a temporary event that is effectively destroyed after the response is given.

    :param model_id: the model id / name to query.
    :type model_id: str
    :param task: the task of the model to load (i.e. text-generation).
    :type task: str
    :param prompt: the prompt to query `model` with.
    :type prompt: str

    :returns: the mode's `response` to `data`
    :rtype: dict"""

    model_id = model_id.replace("\\", "/")
    # TODO: implement *actual* model querying
    # return {model_id: f"My reaction to {prompt}: \*o*/ woo {user.username}!"}
    return {"response": model.generate(model_id, task, prompt)}


@app.post("/create-context/{model_id}/{task}")
async def create_context(model_id: str, task: str, user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Creates a new context with `model_id` and returns it's cid."""
    model_id = model_id.replace("\\", "/")
    cid: int = db.create_context(model_id, task, user.uid)
    return {"detail": f"Successfully created context with {model_id}!", "cid": cid}


# TODO: implement long-polling new prompts to the context to the @app.post version of this exact same route
@app.put("/c/{cid}/{prompt}", status_code=200)
async def update_context(cid: int, prompt: str, response: Response,
                         user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Returns the context model's response to `prompt` with context `cid`. Requires Oauth2"""
    try:
        if db.get_context_owner(cid) != user.uid:  # TODO: implement context.owner != user.uid
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"detail": "You do not own this context"}
        context: Context = Context(**db.get_context(cid))

        history: dict = db.add_to_context({"user": prompt}, cid)
        return model.generate(context.model_id, context.task, history)
    except KeyError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"detail": f"No context could be found under cid: '{cid}'"}


@app.get("/c/{cid}", status_code=200)
async def get_context(cid: int, response: Response, user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Returns the stored context saved under `cid`. Requires Oauth2."""
    # TODO: add security to this!!!
    try:
        context: dict = db.get_context(cid)
        if db.get_context_owner(cid) != user.uid:  # TODO: implement context.owner != user.uid
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"detail": "You do not own this context"}
        return context

    except KeyError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"detail": f"No context could be found under cid: '{cid}'"}


if __name__ == '__main__':
    raise RuntimeError(
        "Run this script with either `fastapi dev` or `uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload` instead!")
