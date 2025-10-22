// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AgentRegistry {
    struct Agent { address owner; string uri; bool active; }
    mapping(uint256 => Agent) public agents;
    event Registered(uint256 indexed id, address owner, string uri);

    function register(uint256 id, string calldata uri) external {
        require(agents[id].owner == address(0), "exists");
        agents[id] = Agent(msg.sender, uri, true);
        emit Registered(id, msg.sender, uri);
    }
}