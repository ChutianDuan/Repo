export interface UserItem {
  id: number;
  name: string;
  created_at: string;
}

export interface UserListData {
  count: number;
  items: UserItem[];
}
