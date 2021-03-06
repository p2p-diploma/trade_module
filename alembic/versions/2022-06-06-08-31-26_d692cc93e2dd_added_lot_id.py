"""added lot id

Revision ID: d692cc93e2dd
Revises: 3b04336b822e
Create Date: 2022-06-06 08:31:26.288955

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d692cc93e2dd"
down_revision = "3b04336b822e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("transaction", sa.Column("lot_id", sa.Integer(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("transaction", "lot_id")
    # ### end Alembic commands ###
